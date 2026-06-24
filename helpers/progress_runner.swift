import AppKit
import Foundation

final class ProgressRunner: NSObject {
    let titleText: String
    let descriptionText: String
    let command: String
    let arguments: [String]

    let window = NSWindow(
        contentRect: NSRect(x: 0, y: 0, width: 520, height: 180),
        styleMask: [.titled, .closable],
        backing: .buffered,
        defer: false
    )
    let titleLabel = NSTextField(labelWithString: "")
    let detailLabel = NSTextField(labelWithString: "")
    let progress = NSProgressIndicator()
    var process: Process?

    init(title: String, description: String, command: String, arguments: [String]) {
        self.titleText = title
        self.descriptionText = description
        self.command = command
        self.arguments = arguments
    }

    func run() {
        NSApp.setActivationPolicy(.regular)
        buildWindow()
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        startProcess()
    }

    func buildWindow() {
        window.title = titleText
        window.center()
        window.isReleasedWhenClosed = false

        let content = NSView(frame: NSRect(x: 0, y: 0, width: 520, height: 180))
        window.contentView = content

        titleLabel.stringValue = descriptionText
        titleLabel.font = NSFont.boldSystemFont(ofSize: 16)
        titleLabel.frame = NSRect(x: 28, y: 128, width: 464, height: 24)
        content.addSubview(titleLabel)

        detailLabel.stringValue = "Preparing…"
        detailLabel.font = NSFont.systemFont(ofSize: 13)
        detailLabel.lineBreakMode = .byTruncatingMiddle
        detailLabel.frame = NSRect(x: 28, y: 82, width: 464, height: 40)
        content.addSubview(detailLabel)

        progress.frame = NSRect(x: 28, y: 48, width: 464, height: 20)
        progress.style = .bar
        progress.isIndeterminate = true
        progress.startAnimation(nil)
        content.addSubview(progress)
    }

    func startProcess() {
        let task = Process()
        task.executableURL = URL(fileURLWithPath: command)
        task.arguments = arguments

        let pipe = Pipe()
        task.standardOutput = pipe
        task.standardError = pipe
        process = task

        pipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard !data.isEmpty else { return }
            guard let text = String(data: data, encoding: .utf8) else { return }
            let line = text
                .split(whereSeparator: \.isNewline)
                .last
                .map(String.init)?
                .trimmingCharacters(in: .whitespacesAndNewlines)
            guard let line, !line.isEmpty else { return }
            DispatchQueue.main.async {
                self?.detailLabel.stringValue = line
            }
        }

        task.terminationHandler = { task in
            pipe.fileHandleForReading.readabilityHandler = nil
            DispatchQueue.main.async {
                NSApp.terminate(task.terminationStatus)
            }
        }

        do {
            try task.run()
        } catch {
            detailLabel.stringValue = "Failed to start: \(error.localizedDescription)"
            DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
                NSApp.terminate(1)
            }
        }
    }
}

func usage() -> Never {
    fputs("Usage: progress_runner <title> <description> <command> [args...]\n", stderr)
    exit(2)
}

let args = CommandLine.arguments
if args.count < 4 {
    usage()
}

let app = NSApplication.shared
let runner = ProgressRunner(
    title: args[1],
    description: args[2],
    command: args[3],
    arguments: Array(args.dropFirst(4))
)
runner.run()
app.run()
