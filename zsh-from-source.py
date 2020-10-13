#!/usr/bin/env python3

import argparse
import contextlib
import copy
import logging
import os
import shutil
import subprocess
import tarfile
import tempfile

DEFAULT_VERSION = "5.8"
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))


def log(level, msg):
    logging.getLogger("zsh-from-source").log(level, msg)


def which(program):
    return os.getenv(program.upper() + "_EXECUTABLE", program)


@contextlib.contextmanager
def cd(newdir):
    prevdir = os.getcwd()
    try:
        yield os.chdir(os.path.expanduser(newdir))
    finally:
        os.chdir(prevdir)


def build_gdbm(directory, env, install_prefix=None):
    with cd(directory):
        version = "latest"
        subprocess.run(("wget", f"https://ftp.gnu.org/gnu/gdbm/gdbm-{version}.tar.gz")).check_returncode()
        source_dir = None
        with tarfile.open(f"gdbm-{version}.tar.gz", 'r') as tar:
            tar.extractall()
            source_dir = tar.getmembers()[0].name

        with cd(source_dir):
            prefix = install_prefix if install_prefix else os.path.join(os.getcwd(), 'gdbm')
            e = copy.copy(env)
            e["CFLAGS"] = f"{e.get('CFLAGS', '')} -fcommon -fPIC"
            subprocess.run(("./configure", "--enable-shared=no", "--enable-libgdbm-compat",
                            f"--prefix={prefix}"), env=e).check_returncode()
            subprocess.run(("make"), env=e).check_returncode()
            subprocess.run(("make", "check"), env=e).check_returncode()
            subprocess.run(("make", "install"), env=e).check_returncode()
            return prefix


def build_ncurses(directory, env, install_prefix=None):
    with cd(directory):
        version = "6.2"
        subprocess.run(("wget", f"https://ftp.gnu.org/pub/gnu/ncurses/ncurses-{version}.tar.gz")).check_returncode()
        source_dir = None
        with tarfile.open(f"ncurses-{version}.tar.gz", 'r') as tar:
            tar.extractall()
            source_dir = tar.getmembers()[0].name

        with cd(source_dir):
            e = copy.copy(env)
            e["CFLAGS"] = f"{e.get('CFLAGS', '')} -fPIC"
            prefix = install_prefix if install_prefix else os.path.join(os.getcwd(), "ncurses")
            subprocess.run(("./configure", "--without-shared", "--without-debug", "--without-ada", "--without-cxx", "--without-cxx-binding",
                            "--enable-widec", f"--prefix={prefix}"), env=e).check_returncode()
            subprocess.run(("make"), env=e).check_returncode()
            subprocess.run(("make", "install"), env=e).check_returncode()
            home_terminfo = os.path.join(os.path.expanduser('~'), ".terminfo")
            if not os.path.exists(home_terminfo):
                shutil.copytree(os.path.join(prefix, "share", "terminfo"), )
            return prefix


def download_zsh():
    subprocess.run(("wget", f"https://www.zsh.org/pub/zsh-{DEFAULT_VERSION}.tar.xz")).check_returncode()
    with tarfile.open(f"zsh-{DEFAULT_VERSION}.tar.xz", 'r') as tar:
        tar.extractall()
    return os.path.join(os.getcwd(), f"zsh-{DEFAULT_VERSION}")


def build_zsh(source_dir, install_prefix=None):
    with cd(source_dir):
        e = dict(os.environ)
        for name in ("ncurses", "gdbm"):
            d = os.path.join(source_dir, name)
            if not os.path.exists(d):
                os.makedirs(d)
                d = globals()[f"build_{name}"](d, e)
            e['CFLAGS'] = f"{e.get('CFLAGS', '')} -I{d}/include"
            e['LDFLAGS'] = f"{e.get('LDFLAGS', '')} -L{d}/lib"

        configure_cmd_line = ["./configure"]
        if install_prefix:
            configure_cmd_line.append(f"--prefix={install_prefix}")

        configure = subprocess.run(configure_cmd_line, env=e)
        if configure.returncode != 0:
            log(logging.ERROR, configure.stderr)
            configure.check_returncode()

        build = subprocess.run(("make"), env=e)
        if build.returncode != 0:
            log(logging.ERROR, build.stderr)
            build.check_returncode()

        install = subprocess.run(("make", "install"), env=e)
        if install.returncode != 0:
            install.check_returncode()


def create_arg_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", dest="sources",
                        help="path to source if it's already available in system")
    parser.add_argument("--prefix", dest="prefix", help="install prefix")
    return parser


if __name__ == "__main__":
    args = create_arg_parser().parse_args()
    with tempfile.TemporaryDirectory() as wd, cd(wd):
        log(logging.INFO, f"Use {wd} as temporary directory")
        build_zsh(
            os.path.expanduser(args.sources) if args.sources else download_zsh(), args.prefix)
