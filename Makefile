.PHONY: ci rust-fmt-check rust-clippy python-test frontend-lint frontend-typecheck frontend-test terraform-fmt-check

ci: rust-fmt-check rust-clippy python-test frontend-lint frontend-typecheck frontend-test terraform-fmt-check

rust-fmt-check:
	cd backend && cargo fmt -- --check

rust-clippy:
	cd backend && cargo clippy --all-targets -- -D warnings

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
