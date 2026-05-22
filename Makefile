.PHONY: run test test-audio reachy-sim reachy-sim-setup push-cappenz \
	reachy-daemon-install reachy-daemon-uninstall reachy-daemon-start \
	reachy-daemon-stop reachy-daemon-status reachy-daemon-logs reachy-daemon-print

REACHY_DAEMON_SCRIPT = uv run python scripts/reachy_daemon_launchd.py

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

reachy-daemon-install:
	$(REACHY_DAEMON_SCRIPT) install

reachy-daemon-uninstall:
	$(REACHY_DAEMON_SCRIPT) uninstall

reachy-daemon-start:
	$(REACHY_DAEMON_SCRIPT) start

reachy-daemon-stop:
	$(REACHY_DAEMON_SCRIPT) stop

reachy-daemon-status:
	$(REACHY_DAEMON_SCRIPT) status

reachy-daemon-logs:
	tail -f $(HOME)/Library/Logs/chores/reachy-daemon.log \
		$(HOME)/Library/Logs/chores/reachy-daemon.stdout.log \
		$(HOME)/Library/Logs/chores/reachy-daemon.stderr.log

reachy-daemon-print:
	$(REACHY_DAEMON_SCRIPT) print

push-cappenz:
	git push git@github.com:cappenz/chores.git main:main
