import 'package:flutter/material.dart';

class ListaConsultable<T> extends StatefulWidget {
  const ListaConsultable({
    super.key,
    required this.consultar,
    required this.vacio,
    required this.tarjeta,
  });

  final Future<List<T>> Function() consultar;
  final String vacio;
  final Widget Function(BuildContext, T) tarjeta;

  @override
  State<ListaConsultable<T>> createState() => _ListaConsultableState<T>();
}

class _ListaConsultableState<T> extends State<ListaConsultable<T>> {
  late Future<List<T>> _carga = Future.sync(widget.consultar);

  Future<void> _recargar() async {
    final nueva = Future<List<T>>.sync(widget.consultar);
    setState(() => _carga = nueva);
    try {
      await nueva;
    } catch (_) {
      // El mensaje se muestra junto al botón de reintento.
    }
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<List<T>>(
    future: _carga,
    builder: (context, estado) {
      if (estado.hasError) {
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            const Text('No se pudo cargar la información.'),
            const SizedBox(height: 12),
            OutlinedButton(
              onPressed: _recargar,
              child: const Text('Reintentar'),
            ),
          ],
        );
      }
      final datos = estado.data;
      if (datos == null) {
        return const Center(child: CircularProgressIndicator());
      }
      return RefreshIndicator(
        onRefresh: _recargar,
        child: ListView.builder(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 20),
          itemCount: datos.isEmpty ? 1 : datos.length,
          itemBuilder: (context, indice) => datos.isEmpty
              ? Text(widget.vacio)
              : widget.tarjeta(context, datos[indice]),
        ),
      );
    },
  );
}
