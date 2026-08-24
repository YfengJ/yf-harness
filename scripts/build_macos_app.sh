#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
build_dir="${project_root}/build/desktop"
output_app="${project_root}/dist/YF-Harness.app"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This builder creates a macOS .app and must run on macOS." >&2
  exit 1
fi

mkdir -p "${build_dir}" "${project_root}/dist"
find "${build_dir}" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
if [[ -d "${output_app}" ]]; then
  rm -rf -- "${output_app}"
fi

uv sync --extra desktop-build --locked
icon_source="${project_root}/src/yfharness/desktop/assets/app-icon.svg"
iconset="${build_dir}/AppIcon.iconset"
mkdir -p "${iconset}"
for points in 16 32 128 256 512; do
  for scale in 1 2; do
    pixels=$((points * scale))
    suffix=""
    if [[ "${scale}" == "2" ]]; then
      suffix="@2x"
    fi
    sips -s format png -z "${pixels}" "${pixels}" "${icon_source}" \
      --out "${iconset}/icon_${points}x${points}${suffix}.png" >/dev/null
  done
done
iconutil -c icns "${iconset}" -o "${build_dir}/AppIcon.icns"
cp "${project_root}/packaging/pysidedeploy.spec" "${build_dir}/pysidedeploy.spec"

cd "${project_root}"
uv run pyside6-deploy \
  "${project_root}/src/yfharness/desktop/app.py" \
  --config-file "${build_dir}/pysidedeploy.spec" \
  --name "YF-Harness" \
  --mode standalone \
  --force

bundle_plist="${output_app}/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleDisplayName YF-Harness" "${bundle_plist}"
/usr/libexec/PlistBuddy -c "Set :CFBundleName YF-Harness" "${bundle_plist}"
/usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier local.yfharness.desktop" "${bundle_plist}"
codesign --force --deep --sign - "${output_app}"
plutil -lint "${bundle_plist}"
open -W "${output_app}" --args --smoke-test

echo "Built and verified: ${output_app}"
