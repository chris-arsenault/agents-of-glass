.PHONY: ci python-test frontend-lint frontend-typecheck frontend-test terraform-fmt-check

ci: python-test frontend-lint frontend-typecheck frontend-test terraform-fmt-check

python-test:
	PYTHONPATH=src python -m unittest discover -s tests -p 'test_*.py'

frontend-lint:
	cd frontend && pnpm exec eslint .

frontend-typecheck:
	cd frontend && pnpm exec tsc --noEmit

frontend-test:
	cd frontend && pnpm exec vitest run --passWithNoTests

terraform-fmt-check:
	terraform fmt -check -recursive infrastructure/terraform/
