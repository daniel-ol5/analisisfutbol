/// Modelos del asistente de uso (backend: app/asistente/schemas.py).
library;

class PasoProgreso {
  const PasoProgreso({
    required this.clave,
    required this.titulo,
    required this.hecho,
    this.ruta,
    this.soloWeb = false,
    this.disponible = true,
    this.tuRolPuede = true,
    this.nota,
  });

  factory PasoProgreso.fromJson(Map<String, dynamic> j) => PasoProgreso(
        clave: j['clave'] as String,
        titulo: j['titulo'] as String,
        hecho: j['estado'] == 'hecho',
        ruta: j['ruta'] as String?,
        soloWeb: j['solo_web'] as bool? ?? false,
        disponible: j['disponible'] as bool? ?? true,
        tuRolPuede: j['tu_rol_puede'] as bool? ?? true,
        nota: j['nota'] as String?,
      );

  final String clave;
  final String titulo;
  final bool hecho;

  /// Pantalla del celular para hacer el paso; nula si no existe en el móvil.
  final String? ruta;
  final bool soloWeb;
  final bool disponible;
  final bool tuRolPuede;
  final String? nota;
}

class Progreso {
  const Progreso({
    required this.pasos,
    this.siguiente,
    this.partidoId,
    this.asistenteActivo = true,
  });

  factory Progreso.fromJson(Map<String, dynamic> j) {
    final siguiente = j['siguiente'];
    return Progreso(
      pasos: (j['pasos'] as List? ?? const [])
          .cast<Map<String, dynamic>>()
          .map(PasoProgreso.fromJson)
          .toList(),
      siguiente: siguiente is Map<String, dynamic> ? PasoProgreso.fromJson(siguiente) : null,
      partidoId: j['partido_id'] as int?,
      asistenteActivo: j['asistente_activo'] as bool? ?? true,
    );
  }

  final List<PasoProgreso> pasos;
  final PasoProgreso? siguiente;
  final int? partidoId;
  final bool asistenteActivo;

  int get hechos => pasos.where((p) => p.hecho).length;
  int get total => pasos.where((p) => p.disponible).length;
}

class Accion {
  const Accion(this.texto, this.ruta);

  factory Accion.fromJson(Map<String, dynamic> j) =>
      Accion(j['texto'] as String, j['ruta'] as String);

  final String texto;
  final String ruta;
}

class Respuesta {
  const Respuesta(this.texto, this.acciones);

  factory Respuesta.fromJson(Map<String, dynamic> j) => Respuesta(
        j['respuesta'] as String? ?? '',
        (j['acciones'] as List? ?? const [])
            .cast<Map<String, dynamic>>()
            .map(Accion.fromJson)
            .toList(),
      );

  final String texto;
  final List<Accion> acciones;
}

/// Un mensaje del chat. `deUsuario` = lo escribió el usuario.
class MensajeChat {
  const MensajeChat(this.texto, {required this.deUsuario, this.acciones = const []});

  final String texto;
  final bool deUsuario;
  final List<Accion> acciones;

  Map<String, String> aHistorial() =>
      {'rol': deUsuario ? 'usuario' : 'asistente', 'texto': texto};
}
