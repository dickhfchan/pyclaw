import Foundation

enum RiskLevel: String {
    case low, medium, high

    var label: String {
        switch self {
        case .low: return "Safe"
        case .medium: return "Caution"
        case .high: return "Careful"
        }
    }
}

struct CleanItem: Identifiable {
    let id = UUID()
    let name: String
    let size: Int64
}

struct CleanCategory: Identifiable {
    let id = UUID()
    let name: String
    let risk: RiskLevel
    var items: [CleanItem]
    var isSelected: Bool = true

    var totalSize: Int64 { items.reduce(0) { $0 + $1.size } }
}
