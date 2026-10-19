def pytest_addoption(parser):
    parser.addoption("--database", choices=("sqlite", "postgresql", "both"), default="sqlite")
    parser.addoption("--postgres-socket", default=None)


def pytest_generate_tests(metafunc):
    if "database_backend" in metafunc.fixturenames:
        selected = metafunc.config.getoption("--database")
        metafunc.parametrize("database_backend", ["sqlite", "postgresql"] if selected == "both" else [selected])
