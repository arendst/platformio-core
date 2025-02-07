# Copyright (c) 2014-present PlatformIO <contact@platformio.org>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from pathlib import Path

from platformio.run.cli import cli as cmd_run


def test_build_flags(clirunner, validate_cliresult, tmpdir):
    build_flags = [
        ("-D TEST_INT=13", "-DTEST_INT=13"),
        ("-DTEST_SINGLE_MACRO", "-DTEST_SINGLE_MACRO"),
        ('-DTEST_STR_SPACE="Andrew Smith"', '"-DTEST_STR_SPACE=Andrew Smith"'),
    ]

    tmpdir.join("platformio.ini").write(
        """
[env:native]
platform = native
extra_scripts = extra.py
lib_ldf_mode = deep+
build_src_flags = -DI_AM_ONLY_SRC_FLAG
build_flags =
    ; -DCOMMENTED_MACRO
    %s ; inline comment
    """
        % " ".join([f[0] for f in build_flags])
    )

    tmpdir.join("extra.py").write(
        """
Import("projenv")

projenv.Append(CPPDEFINES="POST_SCRIPT_MACRO")
    """
    )

    tmpdir.mkdir("src").join("main.cpp").write(
        """
#ifdef I_AM_ONLY_SRC_FLAG
#include <component.h>
#else
#error "I_AM_ONLY_SRC_FLAG"
#endif

#if !defined(TEST_INT) || TEST_INT != 13
#error "TEST_INT"
#endif

#ifndef TEST_STR_SPACE
#error "TEST_STR_SPACE"
#endif

#ifndef I_AM_COMPONENT
#error "I_AM_COMPONENT"
#endif

#ifndef POST_SCRIPT_MACRO
#error "POST_SCRIPT_MACRO"
#endif

#ifdef COMMENTED_MACRO
#error "COMMENTED_MACRO"
#endif

int main() {
}
"""
    )
    component_dir = tmpdir.mkdir("lib").mkdir("component")
    component_dir.join("component.h").write(
        """
#define I_AM_COMPONENT

#ifndef I_AM_ONLY_SRC_FLAG
#error "I_AM_ONLY_SRC_FLAG"
#endif

void dummy(void);
    """
    )
    component_dir.join("component.cpp").write(
        """
#ifdef I_AM_ONLY_SRC_FLAG
#error "I_AM_ONLY_SRC_FLAG"
#endif

void dummy(void ) {};
    """
    )

    result = clirunner.invoke(cmd_run, ["--project-dir", str(tmpdir), "--verbose"])
    validate_cliresult(result)
    build_output = result.output[result.output.find("Scanning dependencies...") :]
    for flag in build_flags:
        assert flag[1] in build_output, flag


def test_build_unflags(clirunner, validate_cliresult, tmpdir):
    tmpdir.join("platformio.ini").write(
        """
[env:native]
platform = native
build_unflags = -DTMP_MACRO1=45 -I. -DNON_EXISTING_MACRO -lunknownLib -Os
extra_scripts = pre:extra.py
"""
    )

    tmpdir.join("extra.py").write(
        """
Import("env")
env.Append(CPPPATH="%s")
env.Append(CPPDEFINES="TMP_MACRO1")
env.Append(CPPDEFINES=["TMP_MACRO2"])
env.Append(CPPDEFINES=("TMP_MACRO3", 13))
env.Append(CCFLAGS=["-Os"])
env.Append(LIBS=["unknownLib"])
    """
        % str(tmpdir)
    )

    tmpdir.mkdir("src").join("main.c").write(
        """
#ifdef TMP_MACRO1
#error "TMP_MACRO1 should be removed"
#endif

int main() {
}
"""
    )

    result = clirunner.invoke(cmd_run, ["--project-dir", str(tmpdir), "--verbose"])
    validate_cliresult(result)
    build_output = result.output[result.output.find("Scanning dependencies...") :]
    assert "-DTMP_MACRO1" not in build_output
    assert "-Os" not in build_output
    assert str(tmpdir) not in build_output


def test_debug_default_build_flags(clirunner, validate_cliresult, tmpdir):
    tmpdir.join("platformio.ini").write(
        """
[env:native]
platform = native
build_type = debug
"""
    )

    tmpdir.mkdir("src").join("main.c").write(
        """
int main() {
}
"""
    )

    result = clirunner.invoke(cmd_run, ["--project-dir", str(tmpdir), "--verbose"])
    validate_cliresult(result)
    build_output = result.output[result.output.find("Scanning dependencies...") :]
    for line in build_output.split("\n"):
        if line.startswith("gcc"):
            assert all(line.count(flag) == 1 for flag in ("-Og", "-g2", "-ggdb2"))
            assert all(
                line.count("-%s%d" % (flag, level)) == 0
                for flag in ("O", "g", "ggdb")
                for level in (0, 1, 3)
            )
            assert "-Os" not in line


def test_debug_custom_build_flags(clirunner, validate_cliresult, tmpdir):
    custom_debug_build_flags = ("-O3", "-g3", "-ggdb3")

    tmpdir.join("platformio.ini").write(
        """
[env:native]
platform = native
build_type = debug
debug_build_flags = %s
    """
        % " ".join(custom_debug_build_flags)
    )

    tmpdir.mkdir("src").join("main.c").write(
        """
int main() {
}
"""
    )

    result = clirunner.invoke(cmd_run, ["--project-dir", str(tmpdir), "--verbose"])
    validate_cliresult(result)
    build_output = result.output[result.output.find("Scanning dependencies...") :]
    for line in build_output.split("\n"):
        if line.startswith("gcc"):
            assert all(line.count(f) == 1 for f in custom_debug_build_flags)
            assert all(
                line.count("-%s%d" % (flag, level)) == 0
                for flag in ("O", "g", "ggdb")
                for level in (0, 1, 2)
            )
            assert all("-O%s" % optimization not in line for optimization in ("g", "s"))


def test_symlinked_libs(clirunner, validate_cliresult, tmp_path: Path):
    external_pkg_dir = tmp_path / "External"
    external_pkg_dir.mkdir()
    (external_pkg_dir / "External.h").write_text(
        """
#define EXTERNAL 1
"""
    )
    (external_pkg_dir / "library.json").write_text(
        """
{
    "name": "External",
    "version": "1.0.0"
}
"""
    )

    project_dir = tmp_path / "project"
    src_dir = project_dir / "src"
    src_dir.mkdir(parents=True)
    (src_dir / "main.c").write_text(
        """
#include <External.h>
#
#if !defined(EXTERNAL)
#error "EXTERNAL is not defined"
#endif

int main() {
}
"""
    )
    (project_dir / "platformio.ini").write_text(
        """
[env:native]
platform = native
lib_deps = symlink://../External
    """
    )
    result = clirunner.invoke(cmd_run, ["--project-dir", str(project_dir), "--verbose"])
    validate_cliresult(result)
