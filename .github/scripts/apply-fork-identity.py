#!/usr/bin/env python3
"""
Applies fork identity customizations to KernelSU repository files:
- Package name: cc.ha7.v
- Version code base: 30007
- Signature size: 0x02c2
- Signature hash: ad82dabe12c9722dbd256b546584638c92d6e9e989425425d96fa62511775652
"""

import os
import re
import sys

PACKAGE_NAME = "cc.ha7.v"
VERSION_CODE = 30007
EXPECTED_SIZE = "0x02c2"
EXPECTED_HASH = "ad82dabe12c9722dbd256b546584638c92d6e9e989425425d96fa62511775652"


def patch_file(path, modifier_fn, verifier_fn):
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Target file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        original = f.read()

    modified = modifier_fn(original)

    if not verifier_fn(modified):
        raise ValueError(f"Verification failed after patching {path}!")

    if modified != original:
        with open(path, "w", encoding="utf-8") as f:
            f.write(modified)
        print(f"✓ Patched: {path}")
    else:
        print(f"= Already up-to-date: {path}")


def patch_kernel_kbuild():
    def modifier(content: str) -> str:
        # Patch KSU_VERSION expr
        content = re.sub(
            r'(\$\(eval\s+KSU_VERSION=\$\(shell\s+expr\s+)\d+(\s*\+\s*\$\(KSU_GIT_VERSION\)\)\))',
            rf'\g<1>{VERSION_CODE}\2',
            content,
        )
        # Patch KSU_PACKAGE_NAME under isPrBuild == 0
        content = re.sub(
            r'(ifeq\s*\(\$\(KSU_IS_PR_BUILD\),0\)\s*\n\s*KSU_PACKAGE_NAME\s*\?=\s*)[^\n]+',
            rf'\g<1>{PACKAGE_NAME}',
            content,
        )
        # Patch EXPECTED_SIZE and EXPECTED_HASH
        content = re.sub(
            r'(KSU_EXPECTED_SIZE\s*\?=\s*)[^\n]+',
            rf'\g<1>{EXPECTED_SIZE}',
            content,
        )
        content = re.sub(
            r'(KSU_EXPECTED_HASH\s*\?=\s*)[^\n]+',
            rf'\g<1>{EXPECTED_HASH}',
            content,
        )
        return content

    def verifier(content: str) -> bool:
        return (
            f"expr {VERSION_CODE} +" in content
            and f"KSU_PACKAGE_NAME ?= {PACKAGE_NAME}" in content
            and f"KSU_EXPECTED_SIZE ?= {EXPECTED_SIZE}" in content
            and f"KSU_EXPECTED_HASH ?= {EXPECTED_HASH}" in content
        )

    patch_file("kernel/Kbuild", modifier, verifier)


def patch_manager_app():
    def modifier(content: str) -> str:
        return re.sub(
            r'(val\s+defaultManagerPackageName\s*=\s*if\s*\(isPrBuild\)\s*"me\.weishu\.kernelsu\.pr"\s*else\s*")[^"]+(")',
            rf'\g<1>{PACKAGE_NAME}\2',
            content,
        )

    def verifier(content: str) -> bool:
        return f'else "{PACKAGE_NAME}"' in content

    patch_file("manager/app/build.gradle.kts", modifier, verifier)


def patch_manager_root():
    def modifier(content: str) -> str:
        return re.sub(
            r'(return\s+)\d+(\s*\+\s*commitCount)',
            rf'\g<1>{VERSION_CODE}\2',
            content,
        )

    def verifier(content: str) -> bool:
        return f"return {VERSION_CODE} + commitCount" in content

    patch_file("manager/build.gradle.kts", modifier, verifier)


def patch_ksud_build():
    def modifier(content: str) -> str:
        content = re.sub(
            r'(let\s+version_code\s*=\s*)\d+(\s*\+\s*version_code;)',
            rf'\g<1>{VERSION_CODE}\2',
            content,
        )
        content = re.sub(
            r'(cargo:rustc-env=KSU_PACKAGE_NAME=)[^"]+(")',
            rf'\g<1>{PACKAGE_NAME}\2',
            content,
        )
        return content

    def verifier(content: str) -> bool:
        return (
            f"let version_code = {VERSION_CODE} + version_code;" in content
            and f"cargo:rustc-env=KSU_PACKAGE_NAME={PACKAGE_NAME}" in content
        )

    patch_file("userspace/ksud/build.rs", modifier, verifier)


def main():
    print("Applying KernelSU fork identity patches...")
    try:
        patch_kernel_kbuild()
        patch_manager_app()
        patch_manager_root()
        patch_ksud_build()
        print("All fork patches applied and verified successfully.")
    except Exception as e:
        print(f"Error applying fork patches: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
