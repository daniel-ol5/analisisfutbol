/// Modelos de Seguridad y Administración  —  P1.
library;

/// Respuesta de GET y PATCH /seguridad/yo (CU-05).
class Perfil {
  const Perfil({
    required this.id,
    required this.clubId,
    required this.email,
    required this.nombre,
    required this.apellido,
    required this.rol,
    required this.activo,
    required this.clubNombre,
  });

  final int id;
  final int clubId;
  final String email;
  final String nombre;
  final String apellido;
  final String rol;
  final bool activo;
  final String clubNombre;

  factory Perfil.fromJson(Map<String, dynamic> json) => Perfil(
        id: json['id'] as int,
        clubId: json['club_id'] as int,
        email: json['email'] as String,
        nombre: json['nombre'] as String? ?? '',
        apellido: json['apellido'] as String? ?? '',
        rol: json['rol'] as String,
        activo: json['activo'] as bool? ?? true,
        clubNombre: json['club_nombre'] as String? ?? '',
      );

  String get nombreCompleto {
    final completo = '$nombre $apellido'.trim();
    return completo.isEmpty ? email : completo;
  }

  String get rolLegible => switch (rol) {
        'ADMIN' => 'Administrador',
        'DT' => 'Director técnico',
        'ANALISTA' => 'Analista',
        'ASISTENTE' => 'Asistente de campo',
        _ => rol,
      };
}
