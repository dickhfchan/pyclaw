import Foundation

enum OutputParser {
    // Strip ANSI escape codes
    static func stripANSI(_ s: String) -> String {
        let pattern = "\u{1B}\\[[0-9;]*[mGKHFABCDJsu]"
        return s.replacingOccurrences(
            of: pattern,
            with: "",
            options: .regularExpression
        )
    }

    // Parse clean.sh --dry-run output
    static func parseCleanCategories(_ output: String) -> [CleanCategory] {
        var categories: [CleanCategory] = []
        var currentName: String? = nil
        var currentItems: [CleanItem] = []

        let lines = output.components(separatedBy: "\n").map { stripANSI($0) }

        for line in lines {
            let trimmed = line.trimmingCharacters(in: .whitespaces)

            // Category header: "➜  System Caches" or ">> System Caches"
            if trimmed.hasPrefix("➜") || trimmed.hasPrefix(">>") || trimmed.hasPrefix("==") {
                // Save previous category
                if let name = currentName, !currentItems.isEmpty {
                    categories.append(CleanCategory(
                        name: name,
                        risk: riskForCategory(name),
                        items: currentItems
                    ))
                }
                currentName = trimmed
                    .drop(while: { "➜ >=" .contains($0) })
                    .trimmingCharacters(in: .whitespaces)
                currentItems = []
                continue
            }

            // Item line with size: "  some/path  1.2 GB" or "✓ some/path  1.2 GB"
            if let item = parseItemLine(trimmed) {
                currentItems.append(item)
            }
        }

        // Save last category
        if let name = currentName, !currentItems.isEmpty {
            categories.append(CleanCategory(
                name: name,
                risk: riskForCategory(name),
                items: currentItems
            ))
        }

        // If nothing parsed, create synthetic categories from size mentions
        if categories.isEmpty {
            categories = parseSyntheticCategories(lines)
        }

        return categories
    }

    private static func parseItemLine(_ line: String) -> CleanItem? {
        // Match: "path/to/file   1.23 GB" or "✓ name, 12 items, 450 MB"
        let stripped = line
            .trimmingCharacters(in: .whitespaces)
            .replacingOccurrences(of: "✓ ", with: "")
            .replacingOccurrences(of: "✗ ", with: "")

        // Try to find size at end of line
        let sizePattern = #"([\d,.]+)\s*(TB|GB|MB|KB|B)$"#
        guard let regex = try? NSRegularExpression(pattern: sizePattern, options: .caseInsensitive),
              let match = regex.firstMatch(in: stripped, range: NSRange(stripped.startIndex..., in: stripped)) else {
            return nil
        }

        let sizeStr = (stripped as NSString).substring(with: match.range(at: 1))
            .replacingOccurrences(of: ",", with: "")
        let unit = (stripped as NSString).substring(with: match.range(at: 2)).uppercased()

        guard let sizeVal = Double(sizeStr) else { return nil }

        let multiplier: Int64
        switch unit {
        case "TB": multiplier = 1_099_511_627_776
        case "GB": multiplier = 1_073_741_824
        case "MB": multiplier = 1_048_576
        case "KB": multiplier = 1_024
        default:   multiplier = 1
        }

        let bytes = Int64(sizeVal * Double(multiplier))

        // Name is everything before the size
        let nameRange = stripped.startIndex..<(stripped.range(of: sizeStr + " " + unit, options: .backwards)?.lowerBound ?? stripped.endIndex)
        let name = String(stripped[nameRange]).trimmingCharacters(in: .init(charactersIn: " ,"))
        if name.isEmpty { return nil }

        return CleanItem(name: name, size: bytes)
    }

    private static func parseSyntheticCategories(_ lines: [String]) -> [CleanCategory] {
        // Fallback: group all size-bearing lines into a single "Junk Files" category
        var items: [CleanItem] = []
        for line in lines {
            if let item = parseItemLine(line.trimmingCharacters(in: .whitespaces)) {
                items.append(item)
            }
        }
        guard !items.isEmpty else { return [] }
        return [CleanCategory(name: "Junk Files", risk: .medium, items: items)]
    }

    private static func riskForCategory(_ name: String) -> RiskLevel {
        let lower = name.lowercased()
        if lower.contains("system") || lower.contains("log") || lower.contains("cache") { return .medium }
        if lower.contains("trash") || lower.contains("browser") || lower.contains("download") { return .low }
        return .medium
    }

    // Parse purge.sh --dry-run output
    static func parsePurgeItems(_ output: String) -> [PurgeItem] {
        var items: [PurgeItem] = []
        let lines = output.components(separatedBy: "\n").map { stripANSI($0) }
        let sizePattern = #"^(.+?)\s+([\d,.]+)\s*(TB|GB|MB|KB|B)$"#
        guard let regex = try? NSRegularExpression(pattern: sizePattern) else { return [] }

        for line in lines {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            guard let match = regex.firstMatch(in: trimmed, range: NSRange(trimmed.startIndex..., in: trimmed)) else { continue }

            let path = (trimmed as NSString).substring(with: match.range(at: 1))
            let sizeStr = (trimmed as NSString).substring(with: match.range(at: 2)).replacingOccurrences(of: ",", with: "")
            let unit = (trimmed as NSString).substring(with: match.range(at: 3)).uppercased()

            guard let sizeVal = Double(sizeStr) else { continue }
            let multiplier: Int64
            switch unit {
            case "TB": multiplier = 1_099_511_627_776
            case "GB": multiplier = 1_073_741_824
            case "MB": multiplier = 1_048_576
            case "KB": multiplier = 1_024
            default:   multiplier = 1
            }

            let url = URL(fileURLWithPath: path)
            let projectRoot = url.deletingLastPathComponent().path
            let name = url.lastPathComponent

            items.append(PurgeItem(
                projectRoot: projectRoot,
                name: name,
                fullPath: path,
                size: Int64(sizeVal * Double(multiplier))
            ))
        }
        return items
    }

    // Parse optimize.sh --dry-run output
    static func parseOptimizeTasks(_ output: String) -> [OptimizeTask] {
        var tasks: [OptimizeTask] = []
        let lines = output.components(separatedBy: "\n").map { stripANSI($0) }

        for line in lines {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            if trimmed.isEmpty { continue }

            let status: OptimizeTask.Status
            let isFixable: Bool
            var name = trimmed

            if trimmed.hasPrefix("✓") || trimmed.hasPrefix("[OK]") || trimmed.hasPrefix("ok ") {
                status = .pass
                isFixable = false
                name = trimmed.drop(while: { "✓ [OKok]".contains($0) }).trimmingCharacters(in: .whitespaces)
            } else if trimmed.hasPrefix("⚠") || trimmed.hasPrefix("[WARN]") || trimmed.hasPrefix("warn ") {
                status = .warning
                isFixable = true
                name = trimmed.drop(while: { "⚠ [WARNwrn]".contains($0) }).trimmingCharacters(in: .whitespaces)
            } else if trimmed.hasPrefix("✗") || trimmed.hasPrefix("[FAIL]") || trimmed.hasPrefix("fail ") {
                status = .fail
                isFixable = true
                name = trimmed.drop(while: { "✗ [FAILfail]".contains($0) }).trimmingCharacters(in: .whitespaces)
            } else {
                continue
            }

            if name.isEmpty { continue }
            tasks.append(OptimizeTask(
                name: name,
                description: "",
                status: status,
                isFixable: isFixable
            ))
        }
        return tasks
    }
}
