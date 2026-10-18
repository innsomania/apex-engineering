# Docker

Read this when a container is part of the task. It decides whether to use the
environment the project already defines or to leave Docker alone, which is
usually the answer.

Use Docker when the task needs reproducible services, isolated build or test
dependencies, or packaging the project already defines. Prefer the existing
Dockerfile and Compose definitions, and inspect mounts, network access, ports,
credentials, entrypoints, and side effects before running them.

- Do not mount the Docker socket or use privileged mode as a default for an
  agent tool.
- Keep workspace mounts and write access scoped to the operation that needs
  them. Set resource limits where relevant and choose network access
  deliberately.
- Container isolation does not confine the host's other tools. Daemon access
  and kernel isolation are documented security considerations.
  [Docker security](https://docs.docker.com/engine/security/)
- For an authorized container change, verify the affected build or service
  behavior and who owns cleanup. Never delete unrelated containers, volumes,
  images, or user data.
- When required infrastructure is unavailable, stop under the user's
  environment policy. Do not repair the daemon or the OS to make a test pass.

Docker being installed does not justify creating infrastructure. These files
create no container, daemon setting, Compose service, or runtime integration.
