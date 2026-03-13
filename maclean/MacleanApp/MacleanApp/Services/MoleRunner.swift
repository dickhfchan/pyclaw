import Foundation

enum MoleError: LocalizedError {
    case scriptNotFound(String)
    case executionFailed(Int32, String)
    case parseError(String)

    var errorDescription: String? {
        switch self {
        case .scriptNotFound(let path): return "Script not found: \(path)"
        case .executionFailed(let code, let msg): return "Process exited \(code): \(msg)"
        case .parseError(let msg): return "Parse error: \(msg)"
        }
    }
}

actor MoleRunner {
    private var baseEnv: [String: String] {
        var env = ProcessInfo.processInfo.environment
        env["MOLE_DIR"] = BundleLocator.moleDir.path
        env["HOME"] = NSHomeDirectory()
        env["PATH"] = "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:" + BundleLocator.binDir.path
        env["TERM"] = "dumb"
        env["COLORTERM"] = ""
        env["NO_COLOR"] = "1"
        return env
    }

    // Collect all output, stream lines after completion (good for log drawer)
    func run(_ executableURL: URL, args: [String], stdinInput: String? = nil) -> AsyncStream<String> {
        AsyncStream { continuation in
            Task {
                do {
                    let output = try await self.collect(executableURL, args: args, stdinInput: stdinInput)
                    for line in output.components(separatedBy: "\n") {
                        if !line.isEmpty { continuation.yield(line) }
                    }
                } catch {
                    continuation.yield("ERROR: \(error.localizedDescription)")
                }
                continuation.finish()
            }
        }
    }

    // Collect all output into a single string
    func collect(_ executableURL: URL, args: [String], stdinInput: String? = nil) async throws -> String {
        let process = Process()
        process.executableURL = executableURL
        process.arguments = args
        process.environment = baseEnv

        let stdoutPipe = Pipe()
        let stderrPipe = Pipe()
        process.standardOutput = stdoutPipe
        process.standardError = stderrPipe

        if let input = stdinInput {
            let stdinPipe = Pipe()
            process.standardInput = stdinPipe
            if let data = input.data(using: .utf8) {
                stdinPipe.fileHandleForWriting.write(data)
                stdinPipe.fileHandleForWriting.closeFile()
            }
        }

        try process.run()

        // Read data asynchronously to avoid blocking the actor
        let data = try await withCheckedThrowingContinuation { (cont: CheckedContinuation<Data, Error>) in
            DispatchQueue.global().async {
                let d = stdoutPipe.fileHandleForReading.readDataToEndOfFile()
                process.waitUntilExit()
                cont.resume(returning: d)
            }
        }

        guard let output = String(data: data, encoding: .utf8) else {
            throw MoleError.parseError("Non-UTF8 output")
        }
        return output
    }

    // Convenience: run bash script
    func runScript(_ scriptURL: URL, args: [String] = [], stdinInput: String? = nil) -> AsyncStream<String> {
        run(BundleLocator.bash, args: [scriptURL.path] + args, stdinInput: stdinInput)
    }

    func collectScript(_ scriptURL: URL, args: [String] = [], stdinInput: String? = nil) async throws -> String {
        try await collect(BundleLocator.bash, args: [scriptURL.path] + args, stdinInput: stdinInput)
    }
}
