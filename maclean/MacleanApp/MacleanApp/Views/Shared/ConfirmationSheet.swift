import SwiftUI

struct ConfirmationSheet: View {
    let itemCount: Int
    let totalBytes: Int64
    let actionLabel: String
    let onConfirm: () -> Void
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(spacing: 24) {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 44))
                .foregroundStyle(.orange)

            VStack(spacing: 8) {
                Text("Confirm \(actionLabel)")
                    .font(.title2.bold())
                Text("This will permanently remove \(itemCount) item\(itemCount == 1 ? "" : "s") totalling \(SizeLabel.format(totalBytes)).")
                    .font(.body)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
            }

            HStack(spacing: 16) {
                Button("Cancel") {
                    dismiss()
                }
                .keyboardShortcut(.cancelAction)

                Button(actionLabel) {
                    dismiss()
                    onConfirm()
                }
                .buttonStyle(.borderedProminent)
                .tint(.red)
                .keyboardShortcut(.defaultAction)
            }
        }
        .padding(32)
        .frame(width: 380)
    }
}
