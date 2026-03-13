import Foundation

enum ScanState {
    case idle, scanning, ready, executing, done
}

@Observable
class CleanerViewModel {
    var categories: [CleanCategory] = []
    var state: ScanState = .idle
    var logLines: [String] = []
    var showLog = false
    var errorMessage: String? = nil

    var totalSelectedSize: Int64 {
        categories.filter(\.isSelected).reduce(0) { $0 + $1.totalSize }
    }
    var selectedCount: Int {
        categories.filter(\.isSelected).count
    }

    private let runner = MoleRunner()

    func scan() async {
        await MainActor.run { state = .scanning; categories = []; errorMessage = nil }

        let script = BundleLocator.script("clean.sh")
        var output = ""

        // Try dry-run first; fall back to regular run capturing output
        let args = FileManager.default.fileExists(atPath: script.path)
            ? ["--dry-run"] : []

        if FileManager.default.fileExists(atPath: script.path) {
            do {
                output = try await runner.collectScript(script, args: args)
            } catch {
                await MainActor.run {
                    errorMessage = error.localizedDescription
                    state = .idle
                }
                return
            }
        } else {
            // Demo mode when Mole not bundled
            output = demoCleanOutput()
        }

        let parsed = OutputParser.parseCleanCategories(output)
        await MainActor.run {
            categories = parsed
            state = .ready
        }
    }

    func clean() async {
        let script = BundleLocator.script("clean.sh")
        await MainActor.run { state = .executing; logLines = []; showLog = true; errorMessage = nil }

        let stream: AsyncStream<String>
        if FileManager.default.fileExists(atPath: script.path) {
            stream = await runner.runScript(script, stdinInput: "y\n")
        } else {
            stream = AsyncStream { cont in
                cont.yield("Demo: clean complete.")
                cont.finish()
            }
        }

        for await line in stream {
            let stripped = OutputParser.stripANSI(line)
            await MainActor.run { logLines.append(stripped) }
        }
        await MainActor.run { state = .done }
    }

    func toggleCategory(_ id: UUID) {
        if let idx = categories.firstIndex(where: { $0.id == id }) {
            categories[idx].isSelected.toggle()
        }
    }

    private func demoCleanOutput() -> String {
        """
        ➜  System Caches
          /Library/Caches/com.apple.Safari  128 MB
          ~/Library/Caches/CloudKit  45 MB
        ➜  Browser Data
          ~/Library/Safari/Downloads.plist  2 MB
        ➜  Developer Junk
          ~/Library/Developer/Xcode/DerivedData  4.2 GB
        """
    }
}
