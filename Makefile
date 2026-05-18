.PHONY: run test test-audio

run:
	uv run --env-file .env python3 chores.py

test:
	uv run pytest -m "not manual" tests

test-audio:
	CHORES_TEST_AUDIO=1 uv run --env-file .env pytest -m manual tests/manual/test_audio.py -s
