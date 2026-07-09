import 'package:flutter_test/flutter_test.dart';

import 'package:lego_remote/main.dart';

void main() {
  testWidgets('App boots to the scan screen', (WidgetTester tester) async {
    await tester.pumpWidget(const LegoRemoteApp());
    await tester.pump();

    expect(find.text('Find your LEGO robot'), findsOneWidget);
  });
}
