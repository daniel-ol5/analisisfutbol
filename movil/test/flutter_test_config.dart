/// Configuración común de todas las pruebas: flutter test la ejecuta antes de
/// cada archivo de esta carpeta.
library;

import 'dart:async';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

Future<void> testExecutable(FutureOr<void> Function() testMain) async {
  // En pruebas no hay Keystore ni Keychain: almacenamiento seguro en memoria.
  FlutterSecureStorage.setMockInitialValues({});
  await testMain();
}
