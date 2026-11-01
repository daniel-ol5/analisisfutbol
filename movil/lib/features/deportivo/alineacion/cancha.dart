/// Cancha con los titulares en su posición  —  T-053.
///
/// Vertical, como se sostiene el teléfono: el arco propio abajo y el rival
/// arriba. Fichas grandes con borde negro y dorsal en negrita, para leerse al
/// sol (T-023).
library;

import 'package:flutter/material.dart';

import 'modelos.dart';

/// Proporción ancho / largo de una cancha reglamentaria (68 × 105 m).
const _proporcion = 68 / 105;

const _cesped = Color(0xFF1F7A45);
const _cespedClaro = Color(0xFF248A4E);
const _amarilloArquero = Color(0xFFF2C200);

/// Punto de la pantalla donde va un jugador dentro de una cancha de [tamano].
///
/// posY (ancho) va de izquierda a derecha; posX (largo) de abajo, arco
/// propio, hacia arriba, arco rival.
Offset posicionEnPantalla(JugadorAlineado j, Size tamano) => Offset(
      j.posY / 100 * tamano.width,
      (1 - j.posX / 100) * tamano.height,
    );

class Cancha extends StatelessWidget {
  const Cancha({super.key, required this.titulares});

  final List<JugadorAlineado> titulares;

  static const _ficha = 46.0;
  static const _anchoEtiqueta = 84.0;

  @override
  Widget build(BuildContext context) {
    return AspectRatio(
      aspectRatio: _proporcion,
      child: LayoutBuilder(builder: (context, limites) {
        final tamano = limites.biggest;
        return ClipRRect(
          borderRadius: BorderRadius.circular(6),
          child: Stack(
            children: [
              Positioned.fill(child: CustomPaint(painter: _LineasCancha())),
              for (final j in titulares)
                _ubicar(posicionEnPantalla(j, tamano), tamano, FichaJugador(jugador: j)),
            ],
          ),
        );
      }),
    );
  }

  /// Centra la ficha en su punto sin que se salga de la cancha.
  Widget _ubicar(Offset centro, Size tamano, Widget ficha) {
    const mitad = _anchoEtiqueta / 2;
    final izquierda = (centro.dx - mitad).clamp(0.0, tamano.width - _anchoEtiqueta);
    final arriba = (centro.dy - _ficha / 2).clamp(0.0, tamano.height - _ficha - 22);
    return Positioned(left: izquierda, top: arriba, width: _anchoEtiqueta, child: ficha);
  }
}

class FichaJugador extends StatelessWidget {
  const FichaJugador({super.key, required this.jugador});

  final JugadorAlineado jugador;

  @override
  Widget build(BuildContext context) {
    final j = jugador;
    return Semantics(
      label: '${j.dorsal}, ${j.nombre} ${j.apellido}, ${j.posicionLegible}'
          '${j.esCapitan ? ', capitán' : ''}',
      excludeSemantics: true,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Stack(
            clipBehavior: Clip.none,
            children: [
              Container(
                width: Cancha._ficha,
                height: Cancha._ficha,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: j.esArquero ? _amarilloArquero : Colors.white,
                  shape: BoxShape.circle,
                  border: Border.all(color: Colors.black, width: 2.5),
                ),
                child: Text('${j.dorsal}',
                    style: const TextStyle(
                        color: Colors.black,
                        fontSize: 20,
                        fontWeight: FontWeight.w900)),
              ),
              if (j.esCapitan)
                Positioned(
                  right: -6,
                  top: -6,
                  child: Container(
                    key: const Key('insignia-capitan'),
                    width: 22,
                    height: 22,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      color: Colors.black,
                      shape: BoxShape.circle,
                      border: Border.all(color: Colors.white, width: 2),
                    ),
                    child: const Text('C',
                        style: TextStyle(
                            color: Colors.white,
                            fontSize: 12,
                            fontWeight: FontWeight.w900)),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 2),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
            decoration: BoxDecoration(
              color: Colors.black.withValues(alpha: 0.8),
              borderRadius: BorderRadius.circular(3),
            ),
            child: Text(
              j.apellido,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                  color: Colors.white, fontSize: 13, fontWeight: FontWeight.w700),
            ),
          ),
        ],
      ),
    );
  }
}

/// Césped a franjas y las líneas reglamentarias, escaladas al tamaño.
class _LineasCancha extends CustomPainter {
  @override
  void paint(Canvas canvas, Size s) {
    const franjas = 10;
    final alto = s.height / franjas;
    for (var i = 0; i < franjas; i++) {
      canvas.drawRect(
        Rect.fromLTWH(0, i * alto, s.width, alto),
        Paint()..color = i.isEven ? _cesped : _cespedClaro,
      );
    }

    final linea = Paint()
      ..color = Colors.white
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2;
    // Medidas reales en metros, pasadas a la escala de la pantalla.
    double x(double m) => m / 68 * s.width;
    double y(double m) => m / 105 * s.height;

    canvas.drawRect(Offset.zero & s, linea);
    canvas.drawLine(Offset(0, s.height / 2), Offset(s.width, s.height / 2), linea);
    canvas.drawCircle(Offset(s.width / 2, s.height / 2), x(9.15), linea);

    for (final arriba in [true, false]) {
      double fila(double m) => arriba ? y(m) : s.height - y(m);
      // Área grande (40,32 × 16,5 m) y área chica (18,32 × 5,5 m).
      for (final (ancho, largo) in [(40.32, 16.5), (18.32, 5.5)]) {
        canvas.drawRect(
          Rect.fromPoints(
            Offset(s.width / 2 - x(ancho / 2), fila(0)),
            Offset(s.width / 2 + x(ancho / 2), fila(largo)),
          ),
          linea,
        );
      }
      canvas.drawCircle(Offset(s.width / 2, fila(11)), 2.5, Paint()..color = Colors.white);
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
