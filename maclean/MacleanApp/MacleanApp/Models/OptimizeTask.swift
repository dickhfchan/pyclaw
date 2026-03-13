import Foundation

struct OptimizeTask: Identifiable {
    enum Status { case pass, warning, fail }

    let id = UUID()
    let name: String
    let description: String
    var status: Status
    var isFixable: Bool
}

struct PurgeItem: Identifiable {
    let id = UUID()
    let projectRoot: String
    let name: String
    let fullPath: String
    let size: Int64
    var isSelected: Bool = true
}
