import AppKit
import Darwin
import Foundation

final class ProgressRunner: NSObject {
    let titleText: String
    let descriptionText: String
    let command: String
    let arguments: [String]
    let progressEnvName: String?

    let window = NSWindow(
        contentRect: NSRect(x: 0, y: 0, width: 680, height: 180),
        styleMask: [.titled, .closable],
        backing: .buffered,
        defer: false
    )
    let titleLabel = NSTextField(labelWithString: "")
    let detailLabel = NSTextField(labelWithString: "")
    let progress = NSProgressIndicator()
    var process: Process?
    var output = ""
    var progressFileURL: URL?
    var progressTimer: Timer?

    init(
        title: String,
        description: String,
        command: String,
        arguments: [String],
        progressEnvName: String? = nil
    ) {
        self.titleText = title
        self.descriptionText = description
        self.command = command
        self.arguments = arguments
        self.progressEnvName = progressEnvName
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

        let content = NSView(frame: NSRect(x: 0, y: 0, width: 680, height: 180))
        window.contentView = content

        titleLabel.stringValue = descriptionText
        titleLabel.font = NSFont.boldSystemFont(ofSize: 16)
        titleLabel.frame = NSRect(x: 28, y: 128, width: 624, height: 24)
        content.addSubview(titleLabel)

        detailLabel.stringValue = "Preparing…"
        detailLabel.font = NSFont.systemFont(ofSize: 13)
        detailLabel.lineBreakMode = .byTruncatingMiddle
        detailLabel.frame = NSRect(x: 28, y: 82, width: 624, height: 40)
        content.addSubview(detailLabel)

        progress.frame = NSRect(x: 28, y: 48, width: 624, height: 20)
        progress.style = .bar
        if progressEnvName == nil {
            progress.isIndeterminate = true
            progress.startAnimation(nil)
        } else {
            progress.isIndeterminate = false
            progress.minValue = 0
            progress.maxValue = 1
            progress.doubleValue = 0
        }
        content.addSubview(progress)
    }

    func startProcess() {
        let task = Process()
        task.executableURL = URL(fileURLWithPath: command)
        task.arguments = arguments
        if let progressEnvName {
            let fileURL = URL(fileURLWithPath: NSTemporaryDirectory())
                .appendingPathComponent("osa_pdf_renamer_progress_\(UUID().uuidString)")
            progressFileURL = fileURL
            var environment = ProcessInfo.processInfo.environment
            environment[progressEnvName] = fileURL.path
            task.environment = environment
            startProgressPolling(fileURL)
        }

        let pipe = Pipe()
        task.standardOutput = pipe
        task.standardError = pipe
        process = task

        pipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard !data.isEmpty else { return }
            guard let text = String(data: data, encoding: .utf8) else { return }
            self?.output += text
            let line = ProgressRunner.cleanDisplayLine(text)
            guard let line, !line.isEmpty else { return }
            DispatchQueue.main.async {
                self?.detailLabel.stringValue = line
            }
        }

        task.terminationHandler = { task in
            pipe.fileHandleForReading.readabilityHandler = nil
            DispatchQueue.main.async {
                self.progressTimer?.invalidate()
                self.progressTimer = nil
                self.removeProgressFile()
                if self.progressEnvName != nil {
                    self.progress.doubleValue = self.progress.maxValue
                }
                if task.terminationStatus != 0, !self.output.isEmpty {
                    let data = Data(self.output.utf8)
                    FileHandle.standardError.write(data)
                }
                Darwin.exit(task.terminationStatus)
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

    func startProgressPolling(_ fileURL: URL) {
        progressTimer = Timer.scheduledTimer(withTimeInterval: 0.25, repeats: true) { [weak self] _ in
            self?.readProgress(fileURL)
        }
    }

    func readProgress(_ fileURL: URL) {
        guard let text = try? String(contentsOf: fileURL, encoding: .utf8) else {
            return
        }

        let parts = text
            .split(separator: "\t", maxSplits: 2, omittingEmptySubsequences: false)
            .map(String.init)
        guard parts.count >= 2 else {
            return
        }

        let completed = Double(parts[0].trimmingCharacters(in: .whitespacesAndNewlines)) ?? 0
        let total = Double(parts[1].trimmingCharacters(in: .whitespacesAndNewlines)) ?? 0
        let message = parts.count >= 3
            ? parts[2].trimmingCharacters(in: .whitespacesAndNewlines)
            : ""

        if total > 0 {
            progress.maxValue = total
            progress.doubleValue = min(max(completed, 0), total)
            let wholeCompleted = Int(min(max(completed, 0), total))
            let wholeTotal = Int(total)
            if message.isEmpty {
                detailLabel.stringValue = "\(wholeCompleted) of \(wholeTotal)"
            } else {
                detailLabel.stringValue = "\(wholeCompleted) of \(wholeTotal): \(message)"
            }
        } else if !message.isEmpty {
            detailLabel.stringValue = message
        }
    }

    func removeProgressFile() {
        guard let progressFileURL else {
            return
        }
        try? FileManager.default.removeItem(at: progressFileURL)
    }

    static func cleanDisplayLine(_ text: String) -> String? {
        var cleaned = text.replacingOccurrences(
            of: #"\u{001B}\[[0-?]*[ -/]*[@-~]"#,
            with: "",
            options: .regularExpression
        )
        cleaned = cleaned.replacingOccurrences(
            of: #"\[[0-?]*[ -/]*[@-~]"#,
            with: "",
            options: .regularExpression
        )
        cleaned = cleaned.replacingOccurrences(of: "\r", with: "\n")
        cleaned = cleaned.replacingOccurrences(
            of: #"[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏█▉▊▋▌▍▎▏░▒▓■□▪▫◼◻◾◽]+"#,
            with: "",
            options: .regularExpression
        )
        cleaned = cleaned.replacingOccurrences(
            of: #"\s{2,}"#,
            with: " ",
            options: .regularExpression
        )

        return cleaned
            .split(whereSeparator: \.isNewline)
            .last
            .map(String.init)?
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }
}

func usage() -> Never {
    fputs("Usage: progress_runner [--progress-env ENV_NAME] <title> <description> <command> [args...]\n", stderr)
    exit(2)
}

var args = Array(CommandLine.arguments.dropFirst())
var progressEnvName: String?
if args.first == "--progress-env" {
    guard args.count >= 2 else {
        usage()
    }
    progressEnvName = args[1]
    args.removeFirst(2)
}

if args.count < 3 {
    usage()
}

let app = NSApplication.shared
let runner = ProgressRunner(
    title: args[0],
    description: args[1],
    command: args[2],
    arguments: Array(args.dropFirst(3)),
    progressEnvName: progressEnvName
)
runner.run()
app.run()
