/// Cola SQLite e idempotencia de eventos del partido — T-070 (HU-29).
library;

import 'dart:convert';

import 'package:path/path.dart' as p;
import 'package:sqflite/sqflite.dart';

import '../../shared/api/cliente.dart';
import 'modelos.dart';

class EventoPendiente {
  const EventoPendiente({
    required this.clubId,
    required this.partidoId,
    required this.evento,
  });

  final int clubId;
  final int partidoId;
  final EventoCrear evento;
}

class ColaEventos {
  ColaEventos({DatabaseFactory? factory, String? ruta})
    : _factory = factory ?? databaseFactory,
      _ruta = ruta;

  final DatabaseFactory _factory;
  final String? _ruta;
  Database? _base;

  Future<Database> _abrir() async {
    final existente = _base;
    if (existente != null && existente.isOpen) return existente;
    final ruta = _ruta ?? p.join(await getDatabasesPath(), 'areatecnica.db');
    final base = await _factory.openDatabase(
      ruta,
      options: OpenDatabaseOptions(
        version: 1,
        onCreate: (db, _) async {
          await db.execute('''
            CREATE TABLE evento_pendiente (
              club_id INTEGER NOT NULL,
              partido_id INTEGER NOT NULL,
              uuid TEXT NOT NULL,
              capturado_en TEXT NOT NULL,
              payload TEXT NOT NULL,
              PRIMARY KEY (club_id, uuid)
            )
          ''');
          await db.execute('''
            CREATE INDEX ix_evento_pendiente_orden
            ON evento_pendiente (club_id, partido_id, capturado_en, uuid)
          ''');
        },
      ),
    );
    _base = base;
    return base;
  }

  Future<void> encolar({
    required int clubId,
    required int partidoId,
    required EventoCrear evento,
  }) async {
    if (evento.uuid == null || evento.capturadoEn == null) {
      throw ArgumentError('El evento pendiente requiere UUID y marca temporal');
    }
    final db = await _abrir();
    await db.insert('evento_pendiente', {
      'club_id': clubId,
      'partido_id': partidoId,
      'uuid': evento.uuid,
      'capturado_en': evento.capturadoEn!.toUtc().toIso8601String(),
      'payload': jsonEncode(evento.toJson()),
    }, conflictAlgorithm: ConflictAlgorithm.ignore);
  }

  Future<List<EventoPendiente>> listar({
    required int clubId,
    required int partidoId,
  }) async {
    final db = await _abrir();
    final filas = await db.query(
      'evento_pendiente',
      where: 'club_id = ? AND partido_id = ?',
      whereArgs: [clubId, partidoId],
      orderBy: 'capturado_en ASC, uuid ASC',
    );
    return filas.map((fila) {
      final payload = jsonDecode(fila['payload'] as String);
      return EventoPendiente(
        clubId: fila['club_id'] as int,
        partidoId: fila['partido_id'] as int,
        evento: EventoCrear.fromJson(payload as Map<String, dynamic>),
      );
    }).toList();
  }

  Future<int> contar({required int clubId, required int partidoId}) async {
    final db = await _abrir();
    final resultado = await db.rawQuery(
      '''
        SELECT COUNT(*) AS cantidad
        FROM evento_pendiente
        WHERE club_id = ? AND partido_id = ?
      ''',
      [clubId, partidoId],
    );
    return Sqflite.firstIntValue(resultado) ?? 0;
  }

  Future<void> confirmar({required int clubId, required String uuid}) async {
    final db = await _abrir();
    await db.delete(
      'evento_pendiente',
      where: 'club_id = ? AND uuid = ?',
      whereArgs: [clubId, uuid],
    );
  }

  Future<void> cerrar() async {
    final db = _base;
    _base = null;
    if (db != null && db.isOpen) await db.close();
  }
}

typedef RegistrarRemoto =
    Future<EventoManual> Function(int partidoId, EventoCrear evento);
typedef SincronizarRemoto =
    Future<List<EventoManual>> Function(
      int partidoId,
      List<EventoCrear> eventos,
    );

class ResultadoSincronizacion {
  const ResultadoSincronizacion({
    required this.confirmados,
    required this.pendientes,
    this.error,
  });

  final int confirmados;
  final int pendientes;
  final Object? error;
}

class GestorEventosOffline {
  GestorEventosOffline({
    required this.cola,
    required this.registrarRemoto,
    required this.sincronizarRemoto,
    DateTime Function()? reloj,
    String Function()? generarUuid,
  }) : _reloj = reloj ?? DateTime.now,
       _generarUuid = generarUuid;

  final ColaEventos cola;
  final RegistrarRemoto registrarRemoto;
  final SincronizarRemoto sincronizarRemoto;
  final DateTime Function() _reloj;
  final String Function()? _generarUuid;

  Future<EventoManual> registrar({
    required int clubId,
    required int partidoId,
    required EventoCrear evento,
    int minutoEstimado = 0,
  }) async {
    final identificado = evento.conIdentidad(
      reloj: _reloj,
      generarUuid: _generarUuid,
    );
    await cola.encolar(
      clubId: clubId,
      partidoId: partidoId,
      evento: identificado,
    );
    try {
      final confirmado = await registrarRemoto(partidoId, identificado);
      await cola.confirmar(clubId: clubId, uuid: identificado.uuid!);
      return confirmado;
    } catch (error) {
      if (!_esTransitorio(error)) {
        await cola.confirmar(clubId: clubId, uuid: identificado.uuid!);
        rethrow;
      }
      return EventoManual.pendiente(
        partidoId: partidoId,
        evento: identificado,
        minutoEstimado: minutoEstimado,
      );
    }
  }

  Future<ResultadoSincronizacion> sincronizar({
    required int clubId,
    required int partidoId,
  }) async {
    final pendientes = await cola.listar(clubId: clubId, partidoId: partidoId);
    var confirmados = 0;
    Object? ultimoError;
    for (final pendiente in pendientes) {
      try {
        final respuesta = await sincronizarRemoto(partidoId, [
          pendiente.evento,
        ]);
        final uuid = pendiente.evento.uuid!;
        if (!respuesta.any((evento) => evento.uuid == uuid)) {
          ultimoError = StateError('El servidor no confirmó el UUID $uuid');
          break;
        }
        await cola.confirmar(clubId: clubId, uuid: uuid);
        confirmados++;
      } catch (error) {
        ultimoError = error;
        break;
      }
    }
    return ResultadoSincronizacion(
      confirmados: confirmados,
      pendientes: await cola.contar(clubId: clubId, partidoId: partidoId),
      error: ultimoError,
    );
  }

  Future<void> descartar({required int clubId, required String uuid}) =>
      cola.confirmar(clubId: clubId, uuid: uuid);

  static bool _esTransitorio(Object error) {
    if (error is! ErrorApi) return true;
    return error.codigo == 401 ||
        error.codigo == 408 ||
        error.codigo == 429 ||
        error.codigo >= 500;
  }
}
