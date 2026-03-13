import SwiftUI

struct MetricCardView: View {
    let title: String
    let icon: String
    let iconColor: Color
    let value: String
    let subtitle: String
    let fraction: Double  // 0.0–1.0 for progress bar; -1 to hide

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: icon)
                    .font(.title2)
                    .foregroundStyle(iconColor)
                Spacer()
                Text(value)
                    .font(.title2.bold())
                    .monospacedDigit()
            }
            Text(title)
                .font(.headline)
            Text(subtitle)
                .font(.caption)
                .foregroundStyle(.secondary)
            if fraction >= 0 {
                GeometryReader { geo in
                    ZStack(alignment: .leading) {
                        Capsule().fill(.quaternary).frame(height: 6)
                        Capsule()
                            .fill(barColor)
                            .frame(width: geo.size.width * min(max(fraction, 0), 1), height: 6)
                    }
                }
                .frame(height: 6)
            }
        }
        .padding(16)
        .background(.background.shadow(.drop(color: .black.opacity(0.06), radius: 6, y: 2)))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private var barColor: Color {
        if fraction > 0.85 { return .red }
        if fraction > 0.65 { return .orange }
        return iconColor
    }
}
