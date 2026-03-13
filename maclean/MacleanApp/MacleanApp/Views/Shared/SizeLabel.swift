import SwiftUI

struct SizeLabel: View {
    let bytes: Int64
    var font: Font = .caption
    var color: Color = .secondary

    var body: some View {
        Text(formatBytes(bytes))
            .font(font)
            .foregroundStyle(color)
    }

    static func format(_ bytes: Int64) -> String {
        formatBytes(bytes)
    }
}

private func formatBytes(_ bytes: Int64) -> String {
    let formatter = ByteCountFormatter()
    formatter.allowedUnits = [.useAll]
    formatter.countStyle = .file
    formatter.allowsNonnumericFormatting = false
    return formatter.string(fromByteCount: bytes)
}
