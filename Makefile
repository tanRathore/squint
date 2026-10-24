.PHONY: dev test demo docker android

dev:
	scripts/dev.sh

test:
	cd server && python -m pytest -q
	cd research && python -m pytest -q test_research.py

demo:
	python scripts/demo.py

docker:
	cd server && docker compose up --build

android:
	cd android && gradle testDebugUnitTest assembleDebug
