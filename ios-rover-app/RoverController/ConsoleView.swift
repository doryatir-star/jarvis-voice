import SwiftUI

struct ConsoleView: View {
    @EnvironmentObject var hub: HubManager
    @State private var input: String = ""

    var body: some View {
        VStack(spacing: 0) {
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 2) {
                        ForEach(Array(hub.log.enumerated()), id: \.offset) { i, line in
                            Text(line)
                                .font(.system(.caption, design: .monospaced))
                                .foregroundColor(.green)
                                .id(i)
                        }
                    }
                    .padding(8)
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
                .onChange(of: hub.log.count) { _ in
                    if let last = hub.log.indices.last {
                        withAnimation {
                            proxy.scrollTo(last, anchor: .bottom)
                        }
                    }
                }
            }
            .background(Color.black)

            HStack {
                TextField("forward / claw open / raw 0a0081...", text: $input)
                    .textFieldStyle(.roundedBorder)
                    .autocapitalization(.none)
                    .disableAutocorrection(true)
                    .onSubmit(runInput)
                Button("Run") { runInput() }
                    .buttonStyle(BrickButtonStyle(color: LegoTheme.blue))
                    .frame(width: 90)
            }
            .padding(8)
        }
        .background(LegoTheme.background.ignoresSafeArea())
    }

    private func runInput() {
        ConsoleCommand.run(input, on: hub)
        input = ""
    }
}

/// A tiny command language for the console box — typed shorthand for the
/// same actions the Controller tab's buttons trigger, plus a "raw" escape
/// hatch for sending hand-crafted LWP3 bytes while debugging.
enum ConsoleCommand {
    static func run(_ raw: String, on hub: HubManager) {
        let text = raw.trimmingCharacters(in: .whitespaces).lowercased()
        guard !text.isEmpty else { return }
        let parts = text.split(separator: " ").map(String.init)

        switch parts.first {
        case "forward", "fwd": hub.drive(.forward)
        case "backward", "back": hub.drive(.backward)
        case "left": hub.turn(.left)
        case "right": hub.turn(.right)
        case "stop": hub.stopAll()
        case "head":
            switch parts.count > 1 ? parts[1] : "center" {
            case "left": hub.turnHead(.left)
            case "right": hub.turnHead(.right)
            default: hub.turnHead(.center)
            }
        case "claw":
            if parts.count > 1, parts[1] == "close" {
                hub.claw(.close)
            } else {
                hub.claw(.open)
            }
        case "scan": hub.startScan()
        case "raw":
            hub.sendRaw(hex: parts.dropFirst().joined())
        default:
            hub.addLog("Unknown command: \(text) (try: forward, backward, left, right, stop, head left/right/center, claw open/close, scan, raw <hex>)")
        }
    }
}
