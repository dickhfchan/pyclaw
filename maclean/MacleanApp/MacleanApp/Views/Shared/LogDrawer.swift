import SwiftUI

struct LogDrawer: View {
    let lines: [String]
    @Binding var isShowing: Bool

    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Label("Activity Log", systemImage: "text.alignleft")
                    .font(.headline)
                Spacer()
                Button {
                    withAnimation(.easeInOut(duration: 0.25)) { isShowing = false }
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundStyle(.secondary)
                }
                .buttonStyle(.plain)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 10)
            .background(.bar)

            Divider()

            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 2) {
                        ForEach(Array(lines.enumerated()), id: \.offset) { idx, line in
                            Text(line)
                                .font(.system(.caption, design: .monospaced))
                                .foregroundStyle(lineColor(line))
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .padding(.horizontal, 12)
                                .id(idx)
                        }
                    }
                    .padding(.vertical, 8)
                }
                .onChange(of: lines.count) { _, count in
                    if count > 0 {
                        proxy.scrollTo(count - 1, anchor: .bottom)
                    }
                }
            }
        }
        .frame(height: 220)
        .background(.windowBackground)
        .transition(.move(edge: .bottom))
    }

    private func lineColor(_ line: String) -> Color {
        let lower = line.lowercased()
        if lower.contains("error") || lower.contains("fail") { return .red }
        if lower.contains("warn") { return .orange }
        if lower.contains("ok") || lower.contains("done") || lower.contains("success") { return .green }
        return .primary
    }
}
