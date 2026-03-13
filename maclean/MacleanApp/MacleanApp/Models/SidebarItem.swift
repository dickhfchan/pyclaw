import Foundation

enum SidebarItem: String, CaseIterable, Identifiable {
    case dashboard
    case cleaner
    case diskAnalyzer
    case optimizer
    case purge

    var id: String { rawValue }

    var title: String {
        switch self {
        case .dashboard: return "Dashboard"
        case .cleaner: return "Cleaner"
        case .diskAnalyzer: return "Disk Analyzer"
        case .optimizer: return "Optimizer"
        case .purge: return "Purge"
        }
    }

    var icon: String {
        switch self {
        case .dashboard: return "gauge.medium"
        case .cleaner: return "sparkles"
        case .diskAnalyzer: return "internaldrive"
        case .optimizer: return "bolt.circle"
        case .purge: return "trash.circle"
        }
    }
}
