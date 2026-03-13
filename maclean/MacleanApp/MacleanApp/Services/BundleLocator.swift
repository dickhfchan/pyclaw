import Foundation

enum BundleLocator {
    static var moleDir: URL {
        Bundle.main.resourceURL!.appendingPathComponent("mole")
    }

    static var binDir: URL {
        moleDir.appendingPathComponent("bin")
    }

    static func script(_ name: String) -> URL {
        binDir.appendingPathComponent(name)
    }

    static var analyzeGo: URL {
        moleDir.appendingPathComponent("analyze-go")
    }

    static var bash: URL {
        URL(fileURLWithPath: "/bin/bash")
    }
}
