import SwiftUI

struct TreeMapView: View {
    let node: DiskNode
    let onTap: (DiskNode) -> Void
    let onHoverNode: (DiskNode?) -> Void

    var body: some View {
        GeometryReader { geo in
            let rect = CGRect(origin: .zero, size: geo.size)
            let tiles = squarify(children: node.children ?? [], in: rect)
            ZStack(alignment: .topLeading) {
                ForEach(tiles, id: \.0.id) { (child, tileRect) in
                    TileView(
                        node: child,
                        rect: tileRect,
                        onTap: onTap,
                        onHover: { isHovering in
                            onHoverNode(isHovering ? child : nil)
                        }
                    )
                }
            }
        }
    }

    // Returns [(DiskNode, CGRect)] pairs
    private func squarify(children: [DiskNode], in rect: CGRect) -> [(DiskNode, CGRect)] {
        guard !children.isEmpty, rect.width > 2, rect.height > 2 else { return [] }
        let sorted = children.sorted { $0.size > $1.size }
        let totalSize = sorted.reduce(Int64(0)) { $0 + $1.size }
        guard totalSize > 0 else { return [] }

        var result: [(DiskNode, CGRect)] = []
        subdivide(nodes: sorted, totalSize: totalSize, in: rect, result: &result)
        return result
    }

    private func subdivide(nodes: [DiskNode], totalSize: Int64, in rect: CGRect, result: inout [(DiskNode, CGRect)]) {
        guard !nodes.isEmpty, rect.width > 1, rect.height > 1, totalSize > 0 else { return }

        if nodes.count == 1 {
            result.append((nodes[0], rect))
            return
        }

        // Binary split: find best split point
        var cumSize: Int64 = 0
        var bestIdx = 0
        let half = totalSize / 2
        for (i, n) in nodes.enumerated() {
            cumSize += n.size
            if cumSize >= half {
                bestIdx = i
                break
            }
        }

        let firstGroup = Array(nodes[...bestIdx])
        let secondGroup = Array(nodes[(bestIdx + 1)...])
        let firstSize = firstGroup.reduce(Int64(0)) { $0 + $1.size }
        let secondSize = secondGroup.reduce(Int64(0)) { $0 + $1.size }
        let splitFraction = totalSize > 0 ? CGFloat(firstSize) / CGFloat(totalSize) : 0.5

        let (rect1, rect2): (CGRect, CGRect)
        if rect.width >= rect.height {
            // Split horizontally
            let split = rect.width * splitFraction
            rect1 = CGRect(x: rect.minX, y: rect.minY, width: split, height: rect.height)
            rect2 = CGRect(x: rect.minX + split, y: rect.minY, width: rect.width - split, height: rect.height)
        } else {
            // Split vertically
            let split = rect.height * splitFraction
            rect1 = CGRect(x: rect.minX, y: rect.minY, width: rect.width, height: split)
            rect2 = CGRect(x: rect.minX, y: rect.minY + split, width: rect.width, height: rect.height - split)
        }

        if firstGroup.count == 1 {
            result.append((firstGroup[0], rect1))
        } else {
            subdivide(nodes: firstGroup, totalSize: firstSize, in: rect1, result: &result)
        }

        if secondGroup.isEmpty { return }
        if secondGroup.count == 1 {
            result.append((secondGroup[0], rect2))
        } else {
            subdivide(nodes: secondGroup, totalSize: secondSize, in: rect2, result: &result)
        }
    }
}

private struct TileView: View {
    let node: DiskNode
    let rect: CGRect
    let onTap: (DiskNode) -> Void
    let onHover: (Bool) -> Void
    @State private var isHovered = false

    var body: some View {
        let minDim = min(rect.width, rect.height)

        ZStack {
            RoundedRectangle(cornerRadius: 3)
                .fill(tileColor.opacity(isHovered ? 0.9 : 0.72))
            RoundedRectangle(cornerRadius: 3)
                .strokeBorder(.white.opacity(0.4), lineWidth: 1)

            if minDim > 40 {
                VStack(spacing: 2) {
                    Text(node.name)
                        .font(.system(size: min(12, minDim / 5)))
                        .lineLimit(2)
                        .multilineTextAlignment(.center)
                    if minDim > 60 {
                        Text(SizeLabel.format(node.size))
                            .font(.system(size: min(10, minDim / 6)))
                            .foregroundStyle(.white.opacity(0.8))
                    }
                }
                .foregroundStyle(.white)
                .padding(4)
            }
        }
        .frame(width: rect.width, height: rect.height)
        .offset(x: rect.minX, y: rect.minY)
        .onHover {
            isHovered = $0
            onHover($0)
        }
        .onTapGesture { onTap(node) }
        .help("\(node.name) — \(SizeLabel.format(node.size))")
    }

    private var tileColor: Color {
        let ext = (node.name as NSString).pathExtension.lowercased()
        switch ext {
        case "app": return .blue
        case "pdf", "doc", "docx", "pages", "txt": return .indigo
        case "mp4", "mov", "mp3", "aac", "m4a": return .orange
        case "jpg", "jpeg", "png", "gif", "heic": return .pink
        case "zip", "tar", "gz", "dmg": return .brown
        default:
            let hue = Double(abs(node.name.hashValue) % 360) / 360.0
            return Color(hue: hue, saturation: 0.6, brightness: 0.7)
        }
    }
}
