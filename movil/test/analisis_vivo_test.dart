/// Pruebas unitarias para el módulo de Análisis Táctico en Vivo  —  CU-40 (T-080).
library;

import 'package:areatecnica/features/analisis/modelos.dart';
import 'package:areatecnica/features/analisis/servicio_vivo.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('Modelos de Análisis Táctico (CU-40 / CU-41)', () {
    test('EquipoDetectado parsea correctamente y mapea etiquetas', () {
      expect(EquipoDetectado.desdeTexto('LOCAL'), EquipoDetectado.local);
      expect(EquipoDetectado.desdeTexto('VISITANTE'), EquipoDetectado.visitante);
      expect(EquipoDetectado.desdeTexto('ARBITRO'), EquipoDetectado.arbitro);
      expect(EquipoDetectado.desdeTexto('OTRO'), EquipoDetectado.desconocido);
      expect(EquipoDetectado.local.etiqueta, 'LOCAL');
      expect(EquipoDetectado.visitante.etiqueta, 'VISITANTE');
    });

    test('PosicionDetectada serializa y deserializa JSON', () {
      final json = {
        'tid': 10,
        'equipo': 'LOCAL',
        'x': 52.5,
        'y': 34.0,
        'conf': 0.95,
        'dorsal': 7,
      };

      final pos = PosicionDetectada.fromJson(json);
      expect(pos.tid, 10);
      expect(pos.equipo, EquipoDetectado.local);
      expect(pos.x, 52.5);
      expect(pos.y, 34.0);
      expect(pos.conf, 0.95);
      expect(pos.dorsal, 7);

      final outJson = pos.toJson();
      expect(outJson['tid'], 10);
      expect(outJson['equipo'], 'LOCAL');
      expect(outJson['dorsal'], 7);
    });

    test('IndicadorCalidad deserializa telemetría y alertas de degradación', () {
      final json = {
        'worker_conectado': true,
        'fps': 5.2,
        'jugadores_detectados': 22,
        'balon_visible': false,
        'retraso_s': 0.04,
        'degradado': true,
        'motivo': 'Pérdida temporal de seguimiento del balón',
      };

      final calidad = IndicadorCalidad.fromJson(json);
      expect(calidad.workerConectado, isTrue);
      expect(calidad.fps, 5.2);
      expect(calidad.jugadoresDetectados, 22);
      expect(calidad.balonVisible, isFalse);
      expect(calidad.retrasoS, 0.04);
      expect(calidad.degradado, isTrue);
      expect(calidad.motivo, 'Pérdida temporal de seguimiento del balón');
    });

    test('MensajeWorker parsea frame completo con jugadores y balón', () {
      final frameJson = {
        'partido': 1,
        't': 45.3,
        'jugadores': [
          {'tid': 1, 'equipo': 'LOCAL', 'x': 20.0, 'y': 30.0, 'conf': 0.9, 'dorsal': 1},
          {'tid': 2, 'equipo': 'VISITANTE', 'x': 80.0, 'y': 35.0, 'conf': 0.88, 'dorsal': 9},
        ],
        'balon': {'tid': 99, 'equipo': 'DESCONOCIDO', 'x': 20.5, 'y': 30.2, 'conf': 0.95},
        'calidad': {
          'worker_conectado': true,
          'fps': 5.0,
          'jugadores_detectados': 2,
          'balon_visible': true,
          'retraso_s': 0.02,
          'degradado': false,
        },
      };

      final msg = MensajeWorker.fromJson(frameJson);
      expect(msg.partido, 1);
      expect(msg.t, 45.3);
      expect(msg.jugadores.length, 2);
      expect(msg.balon, isNotNull);
      expect(msg.balon!.x, 20.5);
      expect(msg.calidad.balonVisible, isTrue);
    });

    test('PartidoInfo parsea información del partido y marcador con parte entera o string', () {
      final json = {
        'id': 3,
        'equipo_id': 1,
        'rival': 'Club Rivales F.C.',
        'es_local': true,
        'fecha_hora': '2026-11-10T16:00:00Z',
        'sede': 'Estadio Central',
        'estado': 'EN_CURSO',
        'goles_favor': 2,
        'goles_contra': 1,
        'parte': 0, // En el backend puede llegar como int
        'minuto_actual': 38,
      };

      final p = PartidoInfo.fromJson(json);
      expect(p.id, 3);
      expect(p.rival, 'Club Rivales F.C.');
      expect(p.golesFavor, 2);
      expect(p.golesContra, 1);
      expect(p.parte, '0');
      expect(p.minutoActual, 38);
    });
  });

  group('ServicioPartidoVivo - Reconexión y Posesión (CU-40 / T-080)', () {
    test('Inicializa en estado desconectado y responde a desconectar', () {
      final servicio = ServicioPartidoVivo();
      expect(servicio.estadoConexion, EstadoConexion.desconectado);
      expect(servicio.ultimoMensaje, isNull);
      expect(servicio.posesionLocalPct, 50.0);
      expect(servicio.posesionVisitantePct, 50.0);

      servicio.desconectar();
      expect(servicio.estadoConexion, EstadoConexion.desconectado);
      servicio.dispose();
    });

    test('Criterio de Aceptación T-080: Resiliencia ante desconexión', () async {
      final servicio = ServicioPartidoVivo();

      // Al conectar sin token en el entorno de pruebas, pasa a error/reconectando
      servicio.conectar(1);
      await Future<void>.delayed(const Duration(milliseconds: 50));

      // El servicio maneja la ausencia o caída de red sin lanzar excepciones no controladas
      expect(
        servicio.estadoConexion == EstadoConexion.conectando ||
            servicio.estadoConexion == EstadoConexion.reconectando ||
            servicio.estadoConexion == EstadoConexion.error,
        isTrue,
      );

      // Desconexión limpia
      servicio.desconectar();
      expect(servicio.estadoConexion, EstadoConexion.desconectado);
      servicio.dispose();
    });
  });
}
