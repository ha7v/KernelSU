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


def patch_build_manager():
    def modifier(content: str) -> str:
        if "workflow_dispatch:" not in content:
            content = re.sub(
                r'(workflow_call:\s*\n)',
                r'\1  workflow_dispatch:\n',
                content,
            )

        if "contents: write" not in content:
            content = re.sub(
                r'(\n  repack-manager:\s*\n(?:\s+.*\n)*?\s+runs-on:\s*ubuntu-latest\s*\n)',
                r'\1    permissions:\n      contents: write\n',
                content,
            )

        if "name: Publish Release" not in content:
            release_step = """
      - name: Publish Release
        if: github.event_name != 'pull_request' && (github.ref == 'refs/heads/main' || github.ref == 'refs/heads/dev')
        env:
          GH_TOKEN: ${{ secrets.PAT_TOKEN || secrets.GITHUB_TOKEN }}
        run: |
          APK=$(ls dist/*.apk 2>/dev/null | head -n 1)
          if [ -n "$APK" ] && [ -f "$APK" ]; then
            TAG="continuous"
            TITLE="Continuous Build"
            NOTES="Automated continuous build of KernelSU Manager based on commit \\`${GITHUB_SHA:0:8}\\`."
            if gh release view "$TAG" -R "$GITHUB_REPOSITORY" >/dev/null 2>&1; then
              echo "Updating existing release $TAG..."
              gh release upload "$TAG" "$APK" -R "$GITHUB_REPOSITORY" --clobber
              gh release edit "$TAG" -R "$GITHUB_REPOSITORY" --title "$TITLE" --notes "$NOTES"
            else
              echo "Creating new release $TAG..."
              gh release create "$TAG" "$APK" -R "$GITHUB_REPOSITORY" --title "$TITLE" --notes "$NOTES" --prerelease
            fi
            echo "Release published successfully."
          fi
"""
            content = re.sub(
                r'(\s+- name: Upload build artifact\s*\n[\s\S]*?path:\s*dist/\*\.apk\s*\n)',
                rf'\g<1>{release_step}',
                content,
            )

        return content

    def verifier(content: str) -> bool:
        return (
            "workflow_dispatch:" in content
            and "contents: write" in content
            and "name: Publish Release" in content
        )

    patch_file(".github/workflows/build-manager.yml", modifier, verifier)


def main():
    print("Applying KernelSU fork identity patches...")
    try:
        patch_kernel_kbuild()
        patch_manager_app()
        patch_manager_root()
        patch_ksud_build()
        patch_build_manager()
        print("All fork patches applied and verified successfully.")
    except Exception as e:
        print(f"Error applying fork patches: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
