import Foundation

@Observable
class OptimizerViewModel {
    var tasks: [OptimizeTask] = []
    var state: ScanState = .idle
    var logLines: [String] = []
    var showLog = false
    var errorMessage: String? = nil

    var passCount: Int { tasks.filter { $0.status == .pass }.count }
    var warnCount: Int { tasks.filter { $0.status == .warning }.count }
    var failCount: Int { tasks.filter { $0.status == .fail }.count }

    private let runner = MoleRunner()

    func scan() async {
        await MainActor.run { state = .scanning; tasks = []; errorMessage = nil }

        let script = BundleLocator.script("optimize.sh")

        if FileManager.default.fileExists(atPath: script.path) {
            do {
                let output = try await runner.collectScript(script, args: ["--dry-run"])
                let parsed = OutputParser.parseOptimizeTasks(output)
                await MainActor.run { tasks = parsed; state = .ready }
            } catch {
                await MainActor.run { errorMessage = error.localizedDescription; state = .idle }
            }
        } else {
            let demo = demoTasks()
            await MainActor.run { tasks = demo; state = .ready }
        }
    }

    func fix(_ task: OptimizeTask) async {
        let script = BundleLocator.script("optimize.sh")
        await MainActor.run { showLog = true; logLines = [] }

        let stream: AsyncStream<String>
        if FileManager.default.fileExists(atPath: script.path) {
            stream = await runner.runScript(script, args: ["--fix", task.name])
        } else {
            stream = AsyncStream { cont in
                cont.yield("Demo: fixed \(task.name)")
                cont.finish()
            }
        }

        for await line in stream {
            let stripped = OutputParser.stripANSI(line)
            await MainActor.run { logLines.append(stripped) }
        }

        if let idx = tasks.firstIndex(where: { $0.id == task.id }) {
            await MainActor.run { tasks[idx].status = .pass }
        }
    }

    private func demoTasks() -> [OptimizeTask] {
        [
            OptimizeTask(name: "Check login items", description: "Verifies unnecessary startup items", status: .pass, isFixable: false),
            OptimizeTask(name: "DNS cache", description: "DNS cache may be stale", status: .warning, isFixable: true),
            OptimizeTask(name: "Spotlight index", description: "Spotlight index is healthy", status: .pass, isFixable: false),
            OptimizeTask(name: "Swap memory", description: "High swap usage detected", status: .warning, isFixable: true),
            OptimizeTask(name: "Time Machine", description: "No Time Machine backup configured", status: .fail, isFixable: false)
        ]
    }
}
