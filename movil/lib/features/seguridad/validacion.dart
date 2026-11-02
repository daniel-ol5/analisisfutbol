/// Validación de formularios de Seguridad. Mismas reglas que la web
/// (web/src/features/seguridad/validation.ts): devuelven el mensaje o null.
library;

import 'dart:convert';

const _minPassword = 8;
const _maxPassword = 72;
const _maxNombre = 80;

/// Nombre y apellido: opcionales, máximo 80 caracteres.
String? validarNombre(String? valor, String etiqueta) =>
    (valor ?? '').trim().runes.length > _maxNombre
        ? '$etiqueta no puede superar los $_maxNombre caracteres.'
        : null;

/// De 8 a 72 caracteres y máximo 72 bytes: bcrypt cuenta bytes, y los acentos
/// ocupan más de uno.
String? validarPasswordNueva(String actual, String? nueva) {
  final valor = nueva ?? '';
  final caracteres = valor.runes.length;
  if (caracteres < _minPassword) {
    return 'La contraseña debe tener al menos $_minPassword caracteres.';
  }
  if (caracteres > _maxPassword || utf8.encode(valor).length > _maxPassword) {
    return 'La contraseña no puede superar los $_maxPassword caracteres.';
  }
  if (valor == actual) return 'La nueva contraseña debe ser distinta de la actual.';
  return null;
}

String? validarConfirmacion(String nueva, String? confirmacion) {
  if ((confirmacion ?? '').isEmpty) return 'Confirma la nueva contraseña.';
  return confirmacion == nueva ? null : 'Las contraseñas no coinciden.';
}
