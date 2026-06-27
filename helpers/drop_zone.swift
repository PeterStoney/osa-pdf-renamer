import AppKit
import UniformTypeIdentifiers

final class DropZoneView: NSView {
    var onPDFs: (([String]) -> Void)?
    private var isHighlighted = false {
        didSet {
            needsDisplay = true
        }
    }

    override init(frame frameRect: NSRect) {
        super.init(frame: frameRect)
        registerForDraggedTypes([.fileURL])
        wantsLayer = true
    }

    required init?(coder: NSCoder) {
        super.init(coder: coder)
        registerForDraggedTypes([.fileURL])
        wantsLayer = true
    }

    override func draggingEntered(_ sender: NSDraggingInfo) -> NSDragOperation {
        if pdfPaths(from: sender).isEmpty {
            return []
        }
        isHighlighted = true
        return .copy
    }

    override func draggingExited(_ sender: NSDraggingInfo?) {
        isHighlighted = false
    }

    override func performDragOperation(_ sender: NSDraggingInfo) -> Bool {
        isHighlighted = false
        let paths = pdfPaths(from: sender)
        if paths.isEmpty {
            return false
        }
        onPDFs?(paths)
        return true
    }

    override func draw(_ dirtyRect: NSRect) {
        super.draw(dirtyRect)

        let bounds = bounds.insetBy(dx: 18, dy: 18)
        let path = NSBezierPath(roundedRect: bounds, xRadius: 14, yRadius: 14)
        NSColor(calibratedWhite: isHighlighted ? 0.82 : 0.94, alpha: 1).setFill()
        path.fill()

        let dashPath = NSBezierPath(roundedRect: bounds, xRadius: 14, yRadius: 14)
        dashPath.lineWidth = 2
        dashPath.setLineDash([8, 5], count: 2, phase: 0)
        NSColor.systemBlue.setStroke()
        dashPath.stroke()
    }

    private func pdfPaths(from sender: NSDraggingInfo) -> [String] {
        guard let urls = sender.draggingPasteboard.readObjects(
            forClasses: [NSURL.self],
            options: [.urlReadingFileURLsOnly: true]
        ) as? [URL] else {
            return []
        }

        return urls
            .filter { $0.pathExtension.lowercased() == "pdf" }
            .map { $0.path }
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    private let appBundle: String
    private let progressRunner: String
    private let version: String
    private let formatPreview: String
    private var window: NSWindow?
    private var statusLabel = NSTextField(labelWithString: "Ready")
    private var runButton = NSButton()
    private var selectedPaths: [String] = []

    init(appBundle: String, progressRunner: String, version: String, formatPreview: String) {
        self.appBundle = appBundle
        self.progressRunner = progressRunner
        self.version = version
        self.formatPreview = formatPreview
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)

        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 520, height: 390),
            styleMask: [.titled, .closable, .miniaturizable],
            backing: .buffered,
            defer: false
        )
        window.title = "OSA PDF Renamer"
        window.isReleasedWhenClosed = false
        window.center()
        window.contentView = buildContent()
        window.makeKeyAndOrderFront(nil)
        self.window = window
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }

    private func buildContent() -> NSView {
        let root = NSView(frame: NSRect(x: 0, y: 0, width: 520, height: 390))

        let title = NSTextField(labelWithString: "Rename PDFs")
        title.font = .systemFont(ofSize: 24, weight: .semibold)
        title.frame = NSRect(x: 28, y: 334, width: 300, height: 30)
        root.addSubview(title)

        let subtitle = NSTextField(labelWithString: "Version \(version) - \(formatPreview)")
        subtitle.font = .systemFont(ofSize: 13)
        subtitle.textColor = .secondaryLabelColor
        subtitle.frame = NSRect(x: 28, y: 308, width: 464, height: 22)
        root.addSubview(subtitle)

        let dropZone = DropZoneView(frame: NSRect(x: 24, y: 104, width: 472, height: 188))
        dropZone.onPDFs = { [weak self] paths in
            self?.addPDFs(paths)
        }
        root.addSubview(dropZone)

        let prompt = NSTextField(labelWithString: "Drop PDFs Here")
        prompt.font = .systemFont(ofSize: 20, weight: .semibold)
        prompt.textColor = NSColor(calibratedWhite: 0.05, alpha: 1)
        prompt.alignment = .center
        prompt.frame = NSRect(x: 44, y: 194, width: 432, height: 28)
        root.addSubview(prompt)

        let detail = NSTextField(labelWithString: "Files are renamed in their current folder.")
        detail.font = .systemFont(ofSize: 13)
        detail.textColor = NSColor(calibratedWhite: 0.16, alpha: 1)
        detail.alignment = .center
        detail.frame = NSRect(x: 44, y: 168, width: 432, height: 22)
        root.addSubview(detail)

        statusLabel.font = .systemFont(ofSize: 12)
        statusLabel.textColor = .secondaryLabelColor
        statusLabel.frame = NSRect(x: 28, y: 70, width: 464, height: 22)
        root.addSubview(statusLabel)

        let chooseButton = NSButton(title: "Choose PDFs...", target: self, action: #selector(choosePDFs))
        chooseButton.bezelStyle = .rounded
        chooseButton.frame = NSRect(x: 28, y: 26, width: 120, height: 32)
        root.addSubview(chooseButton)

        runButton = NSButton(title: "Rename", target: self, action: #selector(renameSelected))
        runButton.bezelStyle = .rounded
        runButton.isEnabled = false
        if #available(macOS 11.0, *) {
            runButton.hasDestructiveAction = false
        }
        runButton.frame = NSRect(x: 156, y: 26, width: 92, height: 32)
        root.addSubview(runButton)

        let settingsButton = NSButton(title: "Presets", target: self, action: #selector(showSettings))
        settingsButton.bezelStyle = .rounded
        settingsButton.frame = NSRect(x: 376, y: 26, width: 92, height: 32)
        root.addSubview(settingsButton)

        return root
    }

    @objc private func choosePDFs() {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = true
        panel.canChooseDirectories = false
        panel.canChooseFiles = true
        panel.allowedContentTypes = [.pdf]
        if panel.runModal() == .OK {
            addPDFs(panel.urls.map { $0.path })
        }
    }

    @objc private func renameSelected() {
        runRename(paths: selectedPaths)
    }

    private func addPDFs(_ paths: [String]) {
        let existing = Set(selectedPaths)
        let newPaths = paths
            .filter { $0.lowercased().hasSuffix(".pdf") }
            .filter { !existing.contains($0) }
        selectedPaths.append(contentsOf: newPaths)
        statusLabel.stringValue = "\(selectedPaths.count) PDF file(s) selected"
        updateRenameButton()
    }

    private func clearSelection() {
        selectedPaths.removeAll()
        updateRenameButton()
    }

    private func updateRenameButton() {
        let hasSelection = !selectedPaths.isEmpty
        runButton.isEnabled = hasSelection
        if #available(macOS 11.0, *) {
            runButton.bezelColor = hasSelection ? .systemBlue : nil
        }
    }

    @objc private func showSettings() {
        _ = launchApp(arguments: ["--settings"], wait: false)
    }

    private func runRename(paths: [String]) {
        guard !paths.isEmpty else {
            return
        }
        statusLabel.stringValue = "Renaming \(paths.count) PDF file(s)..."
        runButton.isEnabled = false

        DispatchQueue.global(qos: .userInitiated).async {
            let status = self.launchRename(arguments: paths)
            DispatchQueue.main.async {
                if status == 0 {
                    self.statusLabel.stringValue = "Finished"
                    self.clearSelection()
                } else {
                    self.statusLabel.stringValue = "Rename failed or was cancelled"
                    self.updateRenameButton()
                }
            }
        }
    }

    private func launchRename(arguments: [String]) -> Int32 {
        if FileManager.default.isExecutableFile(atPath: progressRunner) {
            return launch(
                executable: progressRunner,
                arguments: [
                    "--progress-env",
                    "OSA_PDF_RENAMER_PROGRESS_FILE",
                    "OSA PDF Renamer",
                    "Renaming PDFs",
                    "/usr/bin/open",
                    "-W",
                    "-n",
                    appBundle,
                    "--args",
                ] + arguments,
                wait: true
            )
        }
        return launchApp(arguments: arguments, wait: true)
    }

    private func launchApp(arguments: [String], wait: Bool) -> Int32 {
        launch(
            executable: "/usr/bin/open",
            arguments: ["-n", appBundle, "--args"] + arguments,
            wait: wait
        )
    }

    private func launch(executable: String, arguments: [String], wait: Bool) -> Int32 {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: executable)
        process.arguments = arguments
        do {
            try process.run()
            if wait {
                process.waitUntilExit()
                return process.terminationStatus
            }
            return 0
        } catch {
            DispatchQueue.main.async {
                self.statusLabel.stringValue = error.localizedDescription
            }
            return 1
        }
    }
}

let app = NSApplication.shared
let arguments = CommandLine.arguments
let appBundle = arguments.count > 1 ? arguments[1] : ""
let progressRunner = arguments.count > 2 ? arguments[2] : ""
let version = arguments.count > 3 ? arguments[3] : "unknown"
let formatPreview = arguments.count > 4 ? arguments[4] : "Unknown.pdf"
let delegate = AppDelegate(
    appBundle: appBundle,
    progressRunner: progressRunner,
    version: version,
    formatPreview: formatPreview
)
app.delegate = delegate
app.run()
