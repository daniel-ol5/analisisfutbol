const {chromium}=require(process.env.TEMP+'/codex-analisis-qa/node_modules/playwright-core');
const fs=require('fs');
const path=require('path');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1000}}); const errors=[]; const guardados=[];
 page.on('pageerror',e=>{errors.push(e.message);console.log('ERROR',e.message);});
 page.on('console',m=>{if(m.type()==='error')console.log('CONSOLE',m.text());});
 await page.addInitScript(()=>localStorage.setItem('areatecnica.sesion',JSON.stringify({access_token:'fixture-solo-qa',usuario:{id:1,club_id:1,email:'qa@example.com',nombre:'Prueba',apellido:'Local',rol:'ADMIN',activo:true}})));
 const png=fs.readFileSync(path.join(__dirname,'calibracion-prueba-18s/primer-cuadro.png')).toString('base64');
 await page.route('**:8000/api/**',async route=>{
  const p=new URL(route.request().url()).pathname; let data=[];
  const headers={'access-control-allow-origin':'*','access-control-allow-headers':'*','access-control-allow-methods':'GET,POST,OPTIONS'};
  if(p.endsWith('/partidos'))data=[{id:1,equipo_id:1,rival:'PSG',estado:'PROGRAMADO'}];
  if(p.endsWith('/videos'))data=[{id:1,nombre:'Clip de prueba',duracion_s:10,resolucion:'1376x776',estado:'SUBIDO'}];
  if(p.endsWith('/cuadro'))data={imagen_base64:png,tiempo_s:0,cuadro_indice:0,ancho_px:1376,alto_px:776};
  if(p.endsWith('/validar'))data={valida:true,error_medio_m:.4,error_max_m:.8,punto_peor:0,mensaje:'Respuesta ficticia para revisar interfaz'};
  if(p.endsWith('/calibracion')&&route.request().method()==='POST'){
   const body=route.request().postDataJSON();guardados.push(body);
   data={...body,id:1,partido_id:1,valida:body.modo==='MANUAL',matriz_h:null,creada_en:'2026-11-17T00:00:00Z'};
  }
  await route.fulfill({json:data,headers});
 });
 await page.goto('http://127.0.0.1:5174/vision/calibracion');
 await page.waitForTimeout(1000); console.log('Estado inicial:',page.url(),await page.locator('body').innerText());
 await page.getByLabel('Video',{exact:true}).selectOption('1');
 await page.getByRole('button',{name:'Guardar configuración',exact:true}).click();
 await page.getByText('Configuración automática guardada.',{exact:false}).waitFor();
 if(guardados[0].modo!=='AUTOMATICA'||guardados[0].puntos_imagen.length)throw Error('Configuración automática incorrecta');
 await page.screenshot({path:path.join(__dirname,'calibracion-desktop.png'),fullPage:true});
 await page.getByRole('button',{name:'Ver cuadro del video',exact:true}).click();
 await page.getByText('Cuadro #0',{exact:false}).waitFor();
 await page.getByRole('button',{name:'Referencia manual de respaldo',exact:true}).click();
 const referencias=[['Mediocampo banda superior',286,216],['Mediocampo banda inferior',352,662],['Esquina superior derecha',919,155],['Área der. · vértice frontal superior',794,216],['Área der. · vértice frontal inferior',1064,400],['Área der. · unión superior',1001,193],['Área der. · unión inferior',1353,360],['Círculo central con mediocampo (banda opuesta)',299,308]];
 for(const [nombre,x,y] of referencias){
  await page.locator('g.cal-hito').filter({hasText:nombre}).first().click();
  const svg=page.locator('.cal-visor-svg'); const box=await svg.boundingBox();
  await svg.click({position:{x:x/1376*box.width,y:y/776*box.height}});
 }
 await page.getByRole('button',{name:'Guardar configuración',exact:true}).click();
 await page.getByText('Referencia manual guardada y válida.',{exact:false}).waitFor();
 if(guardados[1].puntos_imagen.length!==8||guardados[1].referencia.video_id!==1)throw Error('Referencia manual incorrecta');
 const desktopOverflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
 await page.setViewportSize({width:390,height:844}); await page.waitForTimeout(500);
 const mobileOverflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
 await page.screenshot({path:path.join(__dirname,'calibracion-mobile.png'),fullPage:true});
 const reporte={errors,desktopOverflow,mobileOverflow,configuracionesGuardadas:guardados.map(x=>({modo:x.modo,puntos:x.puntos_imagen.length})),alcance:'Interfaz con API simulada; no mide precisión geométrica'};
 fs.writeFileSync(path.join(__dirname,'qa-calibracion.json'),JSON.stringify(reporte,null,2));
 console.log(JSON.stringify(reporte)); await browser.close();
 if(errors.length||desktopOverflow||mobileOverflow)process.exitCode=1;
})().catch(e=>{console.error(e);process.exit(1)});
