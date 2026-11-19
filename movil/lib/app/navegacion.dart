import 'package:flutter/material.dart';

class Modulo {
  const Modulo(this.ruta, this.nombre, this.icono);

  final String ruta;
  final String nombre;
  final IconData icono;
}

const inicioModulo = Modulo('/', 'Inicio', Icons.grid_view_rounded);
const partidoModulo = Modulo(
  '/partido',
  'Control de partido',
  Icons.stadium_outlined,
);
const analisisModulo = Modulo(
  '/analisis',
  'Análisis táctico',
  Icons.analytics_outlined,
);
const modulos = [
  Modulo('/deportivo', 'Gestión deportiva', Icons.groups_outlined),
  Modulo('/vision', 'Visión y video', Icons.videocam_outlined),
  partidoModulo,
  analisisModulo,
  Modulo('/asistencia', 'Asistencia y reportes', Icons.description_outlined),
  Modulo('/perfil', 'Administración', Icons.shield_outlined),
];

bool esRutaActiva(String ruta, String destino) {
  return ruta == destino || (destino != '/' && ruta.startsWith('$destino/'));
}
