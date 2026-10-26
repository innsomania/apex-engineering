// Minimal POSIX controller for installed model CLIs. No shell is involved.
#include <cerrno>
#include <cstring>
#include <filesystem>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
#include <cstdlib>
#include <unistd.h>

namespace fs = std::filesystem;

int main(int argc, char* argv[]) {
    try {
        std::string host = "codex", task, root, project;
        bool dry_run = false;
        std::vector<std::string> extra;
        for (int i = 1; i < argc; ++i) {
            const std::string option = argv[i];
            if (option == "--") {
                while (++i < argc) extra.emplace_back(argv[i]);
                break;
            }
            if (option == "--help") {
                std::cout << "apex --apex-root DIR --project DIR --task TEXT "
                             "[--host codex|claude|opencode] [--dry-run] [-- HOST_ARGS]\n";
                return 0;
            }
            if (option == "--dry-run") { dry_run = true; continue; }
            if (option != "--host" && option != "--task" &&
                option != "--apex-root" && option != "--project")
                throw std::runtime_error("Unknown option: " + option);
            if (++i == argc) throw std::runtime_error("Missing value for " + option);
            if (option == "--host") host = argv[i];
            else if (option == "--task") task = argv[i];
            else if (option == "--apex-root") root = argv[i];
            else project = argv[i];
        }
        if (host != "codex" && host != "claude" && host != "opencode")
            throw std::runtime_error("Unsupported host: " + host);
        if (task.empty() || root.empty() || project.empty())
            throw std::runtime_error("--task, --apex-root and --project are required");
        const auto source = fs::canonical(root);
        const auto workspace = fs::canonical(project);
        if (!fs::is_directory(workspace) || !fs::is_regular_file(source / "SKILL.md"))
            throw std::runtime_error("Project must be a directory; Apex root must contain SKILL.md");
        const std::string prompt =
            "Use Apex Engineering: read " + (source / "SKILL.md").string() +
            " first, then only references needed for this task. This is a reference directory, "
            "not the target project. Target project: " + workspace.string() +
            ". Keep searches and changes within that target; do not search parent folders. "
            "Preserve all user and project rules. Use the host's existing permissions and "
            "enabled Apex controls.\n\nUser task:\n" + task;
        std::vector<std::string> command{host};
        if (host == "codex") {
            command.emplace_back("-c");
            command.emplace_back("skills.include_instructions=false");
        } else if (host == "opencode") command.emplace_back("run");
        command.insert(command.end(), extra.begin(), extra.end());
        if (host == "claude") command.emplace_back("--");
        command.push_back(prompt);
        if (dry_run) {
            std::cout << "Working directory: " << std::quoted(workspace.string()) << '\n';
            for (const auto& argument : command) std::cout << std::quoted(argument) << '\n';
            return 0;
        }
        fs::current_path(workspace);
        if (::setenv("PWD", workspace.c_str(), 1) != 0)
            throw std::runtime_error(std::string("Cannot set PWD: ") + std::strerror(errno));
        std::vector<char*> arguments;
        for (auto& argument : command) arguments.push_back(argument.data());
        arguments.push_back(nullptr);
        // Replace this process: terminal signals and exit status belong to the host.
        ::execvp(arguments.front(), arguments.data());
        const int error = errno;
        std::cerr << "Cannot start " << host << ": " << std::strerror(error) << '\n';
        return error == ENOENT ? 127 : 126;
    } catch (const std::exception& error) {
        std::cerr << "apex: " << error.what() << '\n';
        return 2;
    }
}
