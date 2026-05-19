.PHONY: run test test-audio reachy-sim reachy-sim-setup

run:
	uv run --env-file .env python3 kitchen_agent.py

test:
	uv run pytest -m "not manual" tests

test-audio:
	CHORES_TEST_AUDIO=1 uv run --env-file .env pytest -m manual tests/manual/test_audio.py -s

reachy-sim-setup:
	uv run python -c 'import pathlib, sysconfig; src = pathlib.Path(sysconfig.get_config_var("LIBDIR")) / sysconfig.get_config_var("LDLIBRARY"); dst = pathlib.Path(".venv/lib") / sysconfig.get_config_var("LDLIBRARY"); dst.parent.mkdir(parents=True, exist_ok=True); dst.unlink(missing_ok=True); dst.symlink_to(src); print(f"Linked {dst} -> {src}")'

reachy-sim: reachy-sim-setup
	uv run mjpython -m reachy_mini.daemon.app.main --sim
