import Foundation

@Observable
class DiskAnalyzerViewModel {
    var root: DiskNode? = nil
    var currentNode: DiskNode? = nil
    var path: [DiskNode] = []
    var state: ScanState = .idle
    var errorMessage: String? = nil

    private let runner = MoleRunner()

    func scan(atPath scanPath: String = NSHomeDirectory()) async {
        await MainActor.run { state = .scanning; root = nil; currentNode = nil; path = []; errorMessage = nil }

        let analyzeGo = BundleLocator.analyzeGo

        if FileManager.default.fileExists(atPath: analyzeGo.path) {
            do {
                let json = try await runner.collect(analyzeGo, args: ["-json", scanPath])
                let data = json.data(using: .utf8) ?? Data()
                let node = try JSONDecoder().decode(DiskNode.self, from: data)
                await MainActor.run {
                    root = node
                    currentNode = node
                    path = [node]
                    state = .ready
                }
            } catch {
                await MainActor.run {
                    errorMessage = error.localizedDescription
                    state = .idle
                }
            }
        } else {
            // Demo mode
            let demo = buildDemoTree()
            await MainActor.run {
                root = demo
                currentNode = demo
                path = [demo]
                state = .ready
            }
        }
    }

    func drillInto(_ node: DiskNode) {
        guard node.isDirectory else { return }
        currentNode = node
        path.append(node)
    }

    func navigateTo(_ node: DiskNode) {
        guard let idx = path.firstIndex(where: { $0.id == node.id }) else { return }
        path = Array(path[...idx])
        currentNode = node
    }

    private func buildDemoTree() -> DiskNode {
        DiskNode(
            name: "Home",
            path: NSHomeDirectory(),
            size: 50_000_000_000,
            children: [
                DiskNode(name: "Documents", path: "~/Documents", size: 10_000_000_000, children: [
                    DiskNode(name: "Projects", path: "~/Documents/Projects", size: 8_000_000_000, children: nil),
                    DiskNode(name: "Photos", path: "~/Documents/Photos", size: 2_000_000_000, children: nil)
                ]),
                DiskNode(name: "Library", path: "~/Library", size: 25_000_000_000, children: [
                    DiskNode(name: "Application Support", path: "~/Library/Application Support", size: 15_000_000_000, children: nil),
                    DiskNode(name: "Caches", path: "~/Library/Caches", size: 8_000_000_000, children: nil),
                    DiskNode(name: "Developer", path: "~/Library/Developer", size: 2_000_000_000, children: nil)
                ]),
                DiskNode(name: "Downloads", path: "~/Downloads", size: 15_000_000_000, children: nil)
            ]
        )
    }
}
