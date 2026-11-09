import 'dart:async';
import 'dart:io';

import 'package:areatecnica/features/partido/cola_eventos.dart';
import 'package:areatecnica/features/partido/modelos.dart';
import 'package:areatecnica/shared/api/cliente.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

EventoCrear _evento(
  String uuid,
  DateTime capturado, {
  TipoEvento tipo = TipoEvento.gol,
}) => EventoCrear(
  uuid: uuid,
  capturadoEn: capturado,
  tipo: tipo,
  equipo: 'LOCAL',
  jugadorId: 9,
);

EventoManual _confirmado(int id, int partidoId, EventoCrear evento) =>
    EventoManual(
      id: id,
      partidoId: partidoId,
      uuid: evento.uuid,
      tipo: evento.tipo,
      equipo: evento.equipo,
      jugadorId: evento.jugadorId,
      minuto: 23,
      creadoEn: evento.capturadoEn!,
    );

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  sqfliteFfiInit();

  late Directory temporal;
  late String ruta;
  late ColaEventos cola;

  setUp(() async {
    temporal = await Directory.systemTemp.createTemp('areatecnica_t070_');
    ruta = '${temporal.path}${Platform.pathSeparator}cola.db';
    cola = ColaEventos(factory: databaseFactoryFfi, ruta: ruta);
  });

  tearDown(() async {
    await cola.cerrar();
    if (await temporal.exists()) await temporal.delete(recursive: true);
  });

  test(
    'SQLite conserva la cola al reiniciar, ordenada y separada por club',
    () async {
      final temprano = _evento(
        'uuid-temprano',
        DateTime.utc(2026, 11, 8, 16, 20),
      );
      final tarde = _evento('uuid-tarde', DateTime.utc(2026, 11, 8, 16, 25));
      final otroClub = _evento('uuid-otro', DateTime.utc(2026, 11, 8, 16, 15));

      await cola.encolar(clubId: 1, partidoId: 7, evento: tarde);
      await cola.encolar(clubId: 1, partidoId: 7, evento: temprano);
      await cola.encolar(clubId: 2, partidoId: 7, evento: otroClub);
      await cola.cerrar();

      cola = ColaEventos(factory: databaseFactoryFfi, ruta: ruta);
      final clubUno = await cola.listar(clubId: 1, partidoId: 7);

      expect(clubUno.map((pendiente) => pendiente.evento.uuid), [
        'uuid-temprano',
        'uuid-tarde',
      ]);
      expect(await cola.contar(clubId: 1, partidoId: 7), 2);
      expect(await cola.contar(clubId: 2, partidoId: 7), 1);
    },
  );

  test(
    'un evento conectado se guarda primero y se elimina al confirmarse',
    () async {
      EventoCrear? enviado;
      final gestor = GestorEventosOffline(
        cola: cola,
        reloj: () => DateTime.utc(2026, 11, 8, 16, 20),
        generarUuid: () => 'uuid-conectado',
        registrarRemoto: (partidoId, evento) async {
          enviado = evento;
          return _confirmado(1, partidoId, evento);
        },
        sincronizarRemoto: (_, _) async => [],
      );

      final respuesta = await gestor.registrar(
        clubId: 1,
        partidoId: 7,
        evento: const EventoCrear(tipo: TipoEvento.gol, equipo: 'LOCAL'),
      );

      expect(enviado?.uuid, 'uuid-conectado');
      expect(enviado?.capturadoEn, DateTime.utc(2026, 11, 8, 16, 20));
      expect(respuesta.pendiente, isFalse);
      expect(await cola.contar(clubId: 1, partidoId: 7), 0);
    },
  );

  test(
    'un corte de cinco minutos conserva y reanuda la cola en orden',
    () async {
      final uuids = ['uuid-1', 'uuid-2'].iterator;
      final instantes = [
        DateTime.utc(2026, 11, 8, 16, 20),
        DateTime.utc(2026, 11, 8, 16, 25),
      ].iterator;
      final enviados = <String>[];
      var intento = 0;
      final gestor = GestorEventosOffline(
        cola: cola,
        generarUuid: () {
          uuids.moveNext();
          return uuids.current;
        },
        reloj: () {
          instantes.moveNext();
          return instantes.current;
        },
        registrarRemoto: (_, _) => throw TimeoutException('sin red'),
        sincronizarRemoto: (partidoId, eventos) async {
          intento++;
          enviados.add(eventos.single.uuid!);
          if (intento == 2) throw TimeoutException('corte durante el envío');
          return [_confirmado(intento, partidoId, eventos.single)];
        },
      );

      final primero = await gestor.registrar(
        clubId: 1,
        partidoId: 7,
        evento: const EventoCrear(tipo: TipoEvento.gol, equipo: 'LOCAL'),
      );
      final segundo = await gestor.registrar(
        clubId: 1,
        partidoId: 7,
        evento: const EventoCrear(tipo: TipoEvento.roja, equipo: 'LOCAL'),
      );
      expect(primero.pendiente, isTrue);
      expect(segundo.pendiente, isTrue);

      final parcial = await gestor.sincronizar(clubId: 1, partidoId: 7);
      expect(parcial.confirmados, 1);
      expect(parcial.pendientes, 1);
      expect(enviados, ['uuid-1', 'uuid-2']);

      final reanudado = await gestor.sincronizar(clubId: 1, partidoId: 7);
      expect(reanudado.confirmados, 1);
      expect(reanudado.pendientes, 0);
      expect(enviados, ['uuid-1', 'uuid-2', 'uuid-2']);
    },
  );

  test('un rechazo confirmado no queda reintentándose en la cola', () async {
    final gestor = GestorEventosOffline(
      cola: cola,
      generarUuid: () => 'uuid-invalido',
      reloj: () => DateTime.utc(2026, 11, 8, 16, 20),
      registrarRemoto: (_, _) => throw ErrorApi(422, 'Evento inválido'),
      sincronizarRemoto: (_, _) async => [],
    );

    await expectLater(
      gestor.registrar(
        clubId: 1,
        partidoId: 7,
        evento: const EventoCrear(tipo: TipoEvento.gol, equipo: 'LOCAL'),
      ),
      throwsA(isA<ErrorApi>()),
    );
    expect(await cola.contar(clubId: 1, partidoId: 7), 0);
  });
}
