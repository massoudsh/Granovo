import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]


def count_batches(socket, database):
    with psycopg.connect(host=str(socket), dbname=database) as conn:
        schemas = conn.execute("SELECT schemaname FROM pg_tables WHERE tablename = 'batches'").fetchall()
        return sum(conn.execute(sql.SQL("SELECT count(*) FROM {}.batches").format(sql.Identifier(schema))).fetchone()[0] for (schema,) in schemas)


def main():
    parser = argparse.ArgumentParser(description="Run tests against a disposable, socket-only PostgreSQL cluster and verify backup restoration")
    parser.add_argument("--bin-dir", type=Path, required=True)
    parser.add_argument("--share-dir", type=Path)
    args = parser.parse_args()
    binaries = args.bin_dir.resolve()
    for command in ("initdb", "pg_ctl", "pg_dump", "pg_restore", "createdb"):
        if not (binaries / command).is_file():
            parser.error(f"PostgreSQL utility missing: {command}")
    runtime = ROOT / ".runtime"
    runtime.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pg-", dir=runtime) as temporary:
        work = Path(temporary)
        socket = work / "socket"
        socket.mkdir(mode=0o700)
        data = work / "data"
        command = [str(binaries / "initdb"), "-D", str(data), "--no-locale", "--encoding=UTF8", "--auth-local=trust", "--auth-host=reject"]
        if args.share_dir:
            command.extend(["-L", str(args.share_dir.resolve())])
        subprocess.run(command, check=True, timeout=30, stdout=subprocess.DEVNULL)
        control = [str(binaries / "pg_ctl"), "-D", str(data)]
        started = False
        try:
            subprocess.run([*control, "-l", str(work / "server.log"), "-o", f"-k {socket} -c listen_addresses='' -c unix_socket_permissions=0700 -c jit=off", "-w", "-t", "20", "start"], check=True, timeout=25)
            started = True
            subprocess.run([sys.executable, "-m", "pytest", "-q", "--database=both", f"--postgres-socket={socket}"], cwd=ROOT, check=True, timeout=90)
            backup = work / "test-backup.dump"
            backup.touch(mode=0o600)
            subprocess.run([str(binaries / "pg_dump"), "-h", str(socket), "-Fc", "-f", str(backup), "postgres"], check=True, timeout=20)
            subprocess.run([str(binaries / "createdb"), "-h", str(socket), "restorecheck"], check=True, timeout=10)
            subprocess.run([str(binaries / "pg_restore"), "-h", str(socket), "-d", "restorecheck", "--exit-on-error", str(backup)], check=True, timeout=20)
            original = count_batches(socket, "postgres")
            restored = count_batches(socket, "restorecheck")
            if not original or restored != original:
                raise RuntimeError("Restored batch counts differ from the source test database")
            print("PostgreSQL backup/restore verified against disposable test data.")
        finally:
            if started or (data / "postmaster.pid").exists():
                subprocess.run([*control, "-m", "fast", "-w", "-t", "20", "stop"], check=True, timeout=25)
    print("Disposable PostgreSQL cluster stopped and removed.")


if __name__ == "__main__":
    main()
