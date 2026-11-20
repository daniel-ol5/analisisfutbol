/// Llamadas del asistente de uso. Pasan por el cliente único (token y
/// renovación) y SOLO hablan con nuestro backend: la clave de OpenAI nunca
/// llega al celular. Es una clase para que las pruebas la reemplacen sin red.
library;

import '../../shared/api/cliente.dart';
import 'asistente_modelos.dart';

/// Igual que en el backend.
const largoMaxPregunta = 500;
const maxHistorial = 6;

class AsistenteApi {
  const AsistenteApi();

  Future<Progreso> progreso() async => Progreso.fromJson(
        await cliente.get('/asistente/progreso', params: {'plataforma': 'movil'})
            as Map<String, dynamic>,
      );

  Future<Respuesta> preguntar(
    String pregunta, {
    required String pantalla,
    required List<MensajeChat> historial,
  }) async =>
      Respuesta.fromJson(await cliente.post('/asistente/preguntar', cuerpo: {
        'pregunta': pregunta,
        'pantalla_actual': pantalla,
        'plataforma': 'movil',
        'historial': [
          for (final m in historial.length > maxHistorial
              ? historial.sublist(historial.length - maxHistorial)
              : historial)
            m.aHistorial(),
        ],
      }) as Map<String, dynamic>);
}
