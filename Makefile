.PHONY: help tf-init tf-plan tf-apply tf-validate \
        mcp-install mcp-test mcp-run \
        ai-install ai-test \
        dataset k8s-namespaces test lint

help:
	@echo "Infrastructure:"
	@echo "  make tf-init       terraform init (infrastructure/terraform)"
	@echo "  make tf-plan       terraform plan"
	@echo "  make tf-apply      terraform apply (costs real AWS money)"
	@echo "  make tf-validate   fmt + validate, all stacks, no AWS calls"
	@echo ""
	@echo "MCP server:"
	@echo "  make mcp-install   create venv + install deps"
	@echo "  make mcp-test      run pytest"
	@echo "  make mcp-run       run the server (stdio transport)"
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
	cd mcp-server && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt pytest

mcp-test:
	cd mcp-server && .venv/bin/pytest -q

mcp-run:
	cd mcp-server && .venv/bin/python server.py

ai-install:
	cd ai-engine && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt pytest

ai-test:
	cd ai-engine && .venv/bin/pytest -q

dataset:
	cd datasets && python3 generate_synthetic_dataset.py --rows 5000 --out generated/telemetry.csv

k8s-namespaces:
	kubectl apply -f kubernetes/namespaces/namespaces.yaml

test: mcp-test ai-test

lint: tf-validate
	python3 -c "import yaml, glob; [list(yaml.safe_load_all(open(f))) for f in glob.glob('kubernetes/**/*.yaml', recursive=True)]" && echo "kubernetes/ YAML OK"
