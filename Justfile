set dotenv-filename := "image-template.env"
set dotenv-load

export image_name := env_var("IMAGE_NAME")
export repo_organization := env_var("REPO_ORGANIZATION")
export image_desc := env_var("IMAGE_DESC")
export image_keywords := env_var("IMAGE_KEYWORDS")
export image_logo_url := env_var("IMAGE_LOGO_URL")
export default_tag := env_var("DEFAULT_TAG")
export bib_image := env_var("BIB_IMAGE")
export qemu_image := env_var("QEMU_IMAGE")

alias build-vm := rebuild-qcow2
alias run-vm := run-vm-qcow2

default:
    @just --list

[group('Checks')]
check:
    #!/usr/bin/env bash
    set -euo pipefail
    just --unstable --fmt --check -f Justfile

[group('Checks')]
test:
    python3 -m unittest discover -s tests -v

[group('Checks')]
lint:
    #!/usr/bin/env bash
    set -euo pipefail
    bash -n build_files/build.sh system_files/usr/bin/g-store system_files/usr/bin/g-mode
    python3 -c 'import json, pathlib, tomllib; json.load(open("catalog/apps.json", encoding="utf-8")); json.load(open("catalog/schema.json", encoding="utf-8")); [tomllib.loads(pathlib.Path(path).read_text(encoding="utf-8")) for path in ("disk_config/disk.toml", "disk_config/iso.toml")]'

[group('Build')]
build target_image=image_name tag=default_tag:
    #!/usr/bin/env bash
    set -euo pipefail

    labels=(
      --label "io.artifacthub.package.deprecated=false"
      --label "io.artifacthub.package.keywords={{ image_keywords }}"
      --label "io.artifacthub.package.license=Apache-2.0"
      --label "org.opencontainers.image.created=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      --label "org.opencontainers.image.description={{ image_desc }}"
      --label "org.opencontainers.image.title=G-OS"
    )

    if [[ -n "{{ image_logo_url }}" ]]; then
      labels+=(--label "io.artifacthub.package.logo-url={{ image_logo_url }}")
    fi

    # Do not publish metadata containing the deliberate starter placeholder.
    if [[ "{{ repo_organization }}" != "CHANGE_ME" ]]; then
      labels+=(--label "org.opencontainers.image.source=https://github.com/{{ repo_organization }}/{{ image_name }}")
      labels+=(--label "org.opencontainers.image.url=https://github.com/{{ repo_organization }}/{{ image_name }}")
      labels+=(--label "org.opencontainers.image.vendor={{ repo_organization }}")
    fi

    podman build --pull=newer "${labels[@]}" --tag "${target_image}:${tag}" --file Containerfile .

[group('Utility')]
image-name:
    @echo "{{ image_name }}"

[group('Utility')]
default-tag:
    @echo "{{ default_tag }}"

[group('Utility')]
clean:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -d output ]]; then
      rm -rf -- output
    fi
    find . -maxdepth 1 -type d -name '_build-*' -exec rm -rf -- {} +

# Bootc Image Builder needs rootful Podman storage. These recipes therefore
# build a separate local rootful image before producing a disk artifact.
[private]
_rootful-build target_image tag:
    sudo podman build --pull=newer --tag "{{ target_image }}:{{ tag }}" --file Containerfile .

[private]
_rootful-load-image target_image tag:
    #!/usr/bin/env bash
    set -euo pipefail

    # Prefer the current rootless build and import it even when an older
    # rootful tag exists. Falling back to rootful storage is useful after a
    # deliberate `just rebuild-qcow2`/`just rebuild-iso`.
    if podman image exists "{{ target_image }}:{{ tag }}"; then
      image_archive="$(mktemp -p "${PWD}" _build-podman.XXXXXXXXXX.tar)"
      trap 'rm -f -- "${image_archive}"' EXIT
      podman save --output "${image_archive}" "{{ target_image }}:{{ tag }}"
      sudo podman load --input "${image_archive}"
      exit 0
    fi

    if sudo podman image exists "{{ target_image }}:{{ tag }}"; then
      exit 0
    fi

    echo "Image {{ target_image }}:{{ tag }} was not found; run 'just build' first." >&2
    exit 2

[private]
_build-disk target_image tag disk_type config:
    #!/usr/bin/env bash
    set -euo pipefail

    build_tmp="$(mktemp -d -p "${PWD}" _build-bib.XXXXXXXXXX)"
    config_path="${PWD}/{{ config }}"
    generated_config=""

    cleanup() {
      if [[ -n "${generated_config}" && -f "${generated_config}" ]]; then
        rm -f -- "${generated_config}"
      fi
      if [[ -d "${build_tmp}" ]]; then
        sudo rm -rf -- "${build_tmp}"
      fi
    }
    trap cleanup EXIT

    if [[ "{{ disk_type }}" == "anaconda-iso" ]]; then
      repository_org="{{ repo_organization }}"
      if [[ "${repository_org}" == "CHANGE_ME" ]]; then
        echo "Set REPO_ORGANIZATION in image-template.env before building an installer ISO." >&2
        exit 2
      fi
      repository_org="${repository_org,,}"
      generated_config="$(mktemp -p "${PWD}" _build-iso.XXXXXXXXXX.toml)"
      sed "s|ghcr.io/CHANGE_ME/g-os|ghcr.io/${repository_org}/{{ image_name }}|g" "${config_path}" > "${generated_config}"
      config_path="${generated_config}"
    fi

    sudo podman run --rm --privileged --pull=newer --net=host \
      --security-opt label=type:unconfined_t \
      --volume "${config_path}:/config.toml:ro" \
      --volume "${build_tmp}:/output" \
      --volume /var/lib/containers/storage:/var/lib/containers/storage \
      "{{ bib_image }}" \
      --type "{{ disk_type }}" \
      --use-librepo=True \
      --rootfs=btrfs \
      "{{ target_image }}:{{ tag }}"

    mkdir -p output
    sudo cp -a "${build_tmp}/." output/
    sudo chown -R "$(id -u):$(id -g)" output

[group('Disk images')]
build-qcow2 target_image=("localhost/" + image_name) tag=default_tag:
    just _rootful-load-image "{{ target_image }}" "{{ tag }}"
    just _build-disk "{{ target_image }}" "{{ tag }}" qcow2 disk_config/disk.toml

[group('Disk images')]
rebuild-qcow2 target_image=("localhost/" + image_name) tag=default_tag:
    just _rootful-build "{{ target_image }}" "{{ tag }}"
    just _build-disk "{{ target_image }}" "{{ tag }}" qcow2 disk_config/disk.toml

[group('Disk images')]
build-iso target_image=("localhost/" + image_name) tag=default_tag:
    just _rootful-load-image "{{ target_image }}" "{{ tag }}"
    just _build-disk "{{ target_image }}" "{{ tag }}" anaconda-iso disk_config/iso.toml

[group('Disk images')]
rebuild-iso target_image=("localhost/" + image_name) tag=default_tag:
    just _rootful-build "{{ target_image }}" "{{ tag }}"
    just _build-disk "{{ target_image }}" "{{ tag }}" anaconda-iso disk_config/iso.toml

# qemux/qemu exposes a noVNC viewer in the browser. /dev/kvm is required, so
# this recipe is intended for a Linux host (or a Linux VM with nested KVM).
[group('Virtual machine')]
run-vm-qcow2:
    #!/usr/bin/env bash
    set -euo pipefail
    image_file="output/qcow2/disk.qcow2"
    if [[ ! -f "${image_file}" ]]; then
      echo "${image_file} was not found; run 'just rebuild-qcow2' first." >&2
      exit 2
    fi
    podman run --rm \
      --publish 127.0.0.1:8006:8006 \
      --env CPU_CORES=4 \
      --env RAM_SIZE=8G \
      --env DISK_SIZE=64G \
      --env TPM=Y \
      --env GPU=Y \
      --cap-add=NET_ADMIN \
      --device=/dev/kvm \
      --device=/dev/net/tun \
      --stop-timeout 120 \
      --volume "${PWD}/${image_file}:/boot.qcow2:Z" \
      "{{ qemu_image }}"

[group('Virtual machine')]
run-vm-iso:
    #!/usr/bin/env bash
    set -euo pipefail
    image_file="output/bootiso/install.iso"
    if [[ ! -f "${image_file}" ]]; then
      echo "${image_file} was not found; run 'just rebuild-iso' first." >&2
      exit 2
    fi
    podman run --rm \
      --publish 127.0.0.1:8006:8006 \
      --env CPU_CORES=4 \
      --env RAM_SIZE=8G \
      --env DISK_SIZE=64G \
      --env TPM=Y \
      --env GPU=Y \
      --cap-add=NET_ADMIN \
      --device=/dev/kvm \
      --device=/dev/net/tun \
      --stop-timeout 120 \
      --volume "${PWD}/${image_file}:/boot.iso:Z" \
      "{{ qemu_image }}"
