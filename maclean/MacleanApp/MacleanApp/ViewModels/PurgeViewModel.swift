import Foundation

@Observable
class PurgeViewModel {
    var items: [PurgeItem] = []
    var state: ScanState = .idle
    var logLines: [String] = []
    var showLog = false
    var errorMessage: String? = nil

    var selectedItems: [PurgeItem] { items.filter(\.isSelected) }
    var totalSelectedSize: Int64 { selectedItems.reduce(0) { $0 + $1.size } }

    var groupedItems: [(root: String, items: [PurgeItem])] {
        let dict = Dictionary(grouping: items, by: \.projectRoot)
        return dict.sorted { $0.key < $1.key }.map { (root: $0.key, items: $0.value) }
    }

    private let runner = MoleRunner()

    func scan() async {
        await MainActor.run { state = .scanning; items = []; errorMessage = nil }

        let script = BundleLocator.script("purge.sh")

        if FileManager.default.fileExists(atPath: script.path) {
            do {
                let output = try await runner.collectScript(script, args: ["--dry-run"])
                let parsed = OutputParser.parsePurgeItems(output)
                await MainActor.run { items = parsed; state = .ready }
            } catch {
                await MainActor.run { errorMessage = error.localizedDescription; state = .idle }
            }
        } else {
            let demo = demoPurgeItems()
            await MainActor.run { items = demo; state = .ready }
        }
    }

    func purge() async {
        let script = BundleLocator.script("purge.sh")
        let pathsToDelete = selectedItems.map(\.fullPath)
        let stdinInput = pathsToDelete.joined(separator: "\n") + "\n"

        await MainActor.run { state = .executing; logLines = []; showLog = true }

        let stream: AsyncStream<String>
        if FileManager.default.fileExists(atPath: script.path) {
            stream = await runner.runScript(script, stdinInput: stdinInput)
        } else {
            stream = AsyncStream { cont in
                for path in pathsToDelete {
                    cont.yield("Demo: would remove \(path)")
                }
                cont.finish()
            }
        }

        for await line in stream {
            let stripped = OutputParser.stripANSI(line)
            await MainActor.run { logLines.append(stripped) }
        }
        await MainActor.run { state = .done; items.removeAll { $0.isSelected } }
    }

    func toggleAll() {
        let allSelected = items.allSatisfy(\.isSelected)
        for idx in items.indices { items[idx].isSelected = !allSelected }
    }

    func toggleItem(_ id: UUID) {
        if let idx = items.firstIndex(where: { $0.id == id }) {
            items[idx].isSelected.toggle()
        }
    }

    private func demoPurgeItems() -> [PurgeItem] {
        [
            PurgeItem(projectRoot: "~/projects/myapp", name: "node_modules", fullPath: "~/projects/myapp/node_modules", size: 1_288_490_188),
            PurgeItem(projectRoot: "~/projects/myapp", name: ".next", fullPath: "~/projects/myapp/.next", size: 356_515_840),
            PurgeItem(projectRoot: "~/projects/other", name: "dist", fullPath: "~/projects/other/dist", size: 93_323_264),
            PurgeItem(projectRoot: "~/projects/other", name: "node_modules", fullPath: "~/projects/other/node_modules", size: 524_288_000)
        ]
    }
}
