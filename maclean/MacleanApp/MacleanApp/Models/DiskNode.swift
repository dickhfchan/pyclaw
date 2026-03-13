import Foundation

struct DiskNode: Identifiable {
    let id: UUID
    let name: String
    let path: String
    let size: Int64
    let children: [DiskNode]?

    var isDirectory: Bool { children != nil }

    // Codable conformance via custom init from JSON
    init(id: UUID = UUID(), name: String, path: String, size: Int64, children: [DiskNode]? = nil) {
        self.id = id
        self.name = name
        self.path = path
        self.size = size
        self.children = children
    }
}

extension DiskNode: Decodable {
    private enum CodingKeys: String, CodingKey {
        case name, path, size, children
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        self.id = UUID()
        self.name = try c.decode(String.self, forKey: .name)
        self.path = try c.decodeIfPresent(String.self, forKey: .path) ?? ""
        self.size = try c.decodeIfPresent(Int64.self, forKey: .size) ?? 0
        self.children = try c.decodeIfPresent([DiskNode].self, forKey: .children)
    }
}
