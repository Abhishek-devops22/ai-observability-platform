# Project needs 3.11+; plain `python3` is whatever's on PATH first, which
# on macOS is often the Xcode CLT's older Python (3.9). Prefer a newer
# interpreter if one's installed, without requiring it.
PYTHON := $(shell command -v python3.13 || command -v python3.12 || command -v python3.11 || command -v python3)

.PHONY: help tf-init tf-plan tf-apply tf-validate \
        mcp-install mcp-test mcp-run mcp-deploy-aws mcp-undeploy-aws \
        mcp-ingress-aws mcp-ingress-undeploy-aws \
        ai-install ai-test \
        local-up local-down \
        dataset k8s-namespaces test lint

help:
	@echo "Environments — see README.md 'Quick start' for the full walkthrough:"
	@echo "  make local-up      docker compose up the local Prometheus/Grafana stack (Path A)"
	@echo "  make local-down    docker compose down the local stack"
	@echo "  make mcp-deploy-aws    kubectl apply the MCP server into a real cluster (Path B)"
	@echo "  make mcp-undeploy-aws  kubectl delete it again"
	@echo "  make mcp-ingress-aws   opt-in: provision a real ALB for it — read the warning first"
	@echo "  make mcp-ingress-undeploy-aws  tear the ALB down again"
	@echo ""
	@echo "Infrastructure:"
	@echo "  make tf-init       terraform init (infrastructure/terraform)"
	@echo "  make tf-plan       terraform plan"
	@echo "  make tf-apply      terraform apply (costs real AWS money)"
	@echo "  make tf-validate   fmt + validate, all stacks, no AWS calls"
	@echo ""
	@echo "MCP server:"
	@echo "  make mcp-install   create venv + install deps"
	@echo "  make mcp-test      run pytest"
	@echo "  make mcp-run       run the server locally (stdio transport)"
	@echo ""
	@echo "AI engine:"
	@echo "  make ai-install    create venv + install deps"
	@echo "  make ai-test       run pytest"
	@echo ""
	@echo "Other:"
	@echo "  make dataset       regenerate the sample telemetry dataset"
	@echo "  make k8s-namespaces  kubectl apply the platform's namespaces"
	@echo "  make test          mcp-test + ai-test"
	@echo "  make lint          tf-validate + kubernetes YAML syntax check"

tf-init:
	cd infrastructure/terraform && terraform init

tf-plan:
	cd infrastructure/terraform && terraform plan

tf-apply:
	cd infrastructure/terraform && terraform apply

tf-validate:
	terraform fmt -check -recursive infrastructure/
	cd infrastructure/terraform && terraform init -backend=false -input=false && terraform validate
	cd infrastructure/backend && terraform init -input=false && terraform validate

mcp-install:
	cd mcp-server && $(PYTHON) -m venv .venv && .venv/bin/pip install -r requirements.txt pytest

mcp-test:
	cd mcp-server && .venv/bin/pytest -q

mcp-run:
	cd mcp-server && .venv/bin/python server.py

mcp-deploy-aws:
	kubectl apply -f kubernetes/namespaces/namespaces.yaml
	kubectl apply -f kubernetes/mcp-server/serviceaccount.yaml
	kubectl apply -f kubernetes/mcp-server/rbac-readonly.yaml
	kubectl apply -f kubernetes/mcp-server/configmap.yaml
	kubectl apply -f kubernetes/mcp-server/deployment.yaml
	kubectl apply -f kubernetes/mcp-server/service.yaml
	@echo ""
	@echo "Deployed with the placeholder image in deployment.yaml — build/push"
	@echo "your own first (see mcp-server/README.md 'Running in-cluster'), then:"
	@echo "  kubectl set image deployment/mcp-server -n mcp-server mcp-server=<your image>"

mcp-undeploy-aws:
	kubectl delete -f kubernetes/mcp-server/service.yaml --ignore-not-found
	kubectl delete -f kubernetes/mcp-server/deployment.yaml --ignore-not-found
	kubectl delete -f kubernetes/mcp-server/configmap.yaml --ignore-not-found
	kubectl delete -f kubernetes/mcp-server/rbac-readonly.yaml --ignore-not-found
	kubectl delete -f kubernetes/mcp-server/rbac-mutate.yaml --ignore-not-found
	kubectl delete -f kubernetes/mcp-server/serviceaccount.yaml --ignore-not-found

# Provisions a real ALB (real AWS cost, and network-reachable even on
# scheme: internal) — the MCP server has no auth of its own. Read
# kubernetes/mcp-server/ingress.yaml's header comment before running
# this; requires the AWS Load Balancer Controller already installed
# (kubernetes/README.md).
mcp-ingress-aws:
	kubectl apply -f kubernetes/mcp-server/ingress.yaml
	@echo ""
	@echo "Provisioning — takes a minute or two. Get the URL with:"
	@echo "  kubectl get ingress mcp-server -n mcp-server -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'"

mcp-ingress-undeploy-aws:
	kubectl delete -f kubernetes/mcp-server/ingress.yaml --ignore-not-found

ai-install:
	cd ai-engine && $(PYTHON) -m venv .venv && .venv/bin/pip install -r requirements.txt pytest

ai-test:
	cd ai-engine && .venv/bin/pytest -q

local-up:
	cd local-dev && docker compose up -d --build

local-down:
	cd local-dev && docker compose down

dataset:
	cd datasets && python3 generate_synthetic_dataset.py --rows 5000 --out generated/telemetry.csv

k8s-namespaces:
	kubectl apply -f kubernetes/namespaces/namespaces.yaml

test: mcp-test ai-test

lint: tf-validate
	python3 -c "import yaml, glob; [list(yaml.safe_load_all(open(f))) for f in glob.glob('kubernetes/**/*.yaml', recursive=True)]" && echo "kubernetes/ YAML OK"
