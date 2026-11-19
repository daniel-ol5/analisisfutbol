import 'package:flutter/material.dart';

import '../../shared/ui/lista_consultable.dart';
import '../deportivo/agenda/selector_partido.dart';
import 'api.dart';

class VisionPagina extends StatelessWidget {
  const VisionPagina({super.key});

  @override
  Widget build(BuildContext context) => DefaultTabController(
    length: 2,
    child: Scaffold(
      appBar: AppBar(
        title: const Text('Visión y video'),
        bottom: const TabBar(
          tabs: [
            Tab(text: 'Grabaciones'),
            Tab(text: 'Montaje'),
          ],
        ),
      ),
      body: TabBarView(
        children: [
          SelectorPartido(
            contenido: (partido) => ListaConsultable<VideoPartido>(
              consultar: () => listarVideos(partido.id),
              vacio:
                  'Este partido aún no tiene grabaciones. Sube el video desde la web.',
              tarjeta: (_, video) => _TarjetaVideo(video),
            ),
          ),
          const _Montaje(),
        ],
      ),
    ),
  );
}

class _TarjetaVideo extends StatelessWidget {
  const _TarjetaVideo(this.video);
  final VideoPartido video;

  @override
  Widget build(BuildContext context) {
    final estado = switch (video.estado) {
      'CARGANDO' => 'Subiendo',
      'SUBIDO' => 'Disponible para procesar',
      'PROCESANDO' when video.enCola => 'En cola',
      'PROCESANDO' => 'Procesando · ${video.progreso} %',
      'PROCESADO' => 'Procesado',
      'ERROR' => 'Falló el procesamiento',
      _ => 'Estado desconocido',
    };
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: Column(
        children: [
          ListTile(
            leading: const Icon(Icons.movie_outlined),
            title: Text(video.nombre),
            subtitle: Text(estado),
          ),
          if (video.estado == 'PROCESANDO' && !video.enCola)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 14),
              child: LinearProgressIndicator(value: video.progreso / 100),
            ),
        ],
      ),
    );
  }
}

class _Montaje extends StatelessWidget {
  const _Montaje();

  @override
  Widget build(BuildContext context) => ListView(
    padding: const EdgeInsets.all(16),
    children: const [
      Card(
        child: ListTile(
          leading: Icon(Icons.location_on_outlined),
          title: Text('Ubicación'),
          subtitle: Text(
            'Coloca la cámara en un punto elevado, alineado con el mediocampo.',
          ),
        ),
      ),
      Card(
        child: ListTile(
          leading: Icon(Icons.fit_screen_rounded),
          title: Text('Encuadre'),
          subtitle: Text(
            'Comprueba que se vean las cuatro esquinas y las líneas de banda.',
          ),
        ),
      ),
      Card(
        child: ListTile(
          leading: Icon(Icons.videocam_outlined),
          title: Text('Captura'),
          subtitle: Text(
            'Revisa la estabilidad de la cámara y el enfoque antes de grabar.',
          ),
        ),
      ),
    ],
  );
}
