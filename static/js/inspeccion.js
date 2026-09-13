/**
 * Inspección visual de chapa: click sobre la foto de una vista para ubicar
 * un marcador de daño (golpe, rayón, etc). El click se convierte en
 * coordenadas relativas (%) sobre la imagen, así el marcador queda bien
 * ubicado sin importar el tamaño de pantalla.
 */
document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll(".vista-imgwrap").forEach(function (wrap) {
    wrap.addEventListener("click", function (ev) {
      if (ev.target.classList.contains("marcador-dot")) return;

      var rect = wrap.getBoundingClientRect();
      var x = ((ev.clientX - rect.left) / rect.width) * 100;
      var y = ((ev.clientY - rect.top) / rect.height) * 100;
      x = Math.min(100, Math.max(0, x));
      y = Math.min(100, Math.max(0, y));

      var vista = wrap.id.replace("wrap-", "");
      var posx = document.getElementById("posx-" + vista);
      var posy = document.getElementById("posy-" + vista);
      if (posx) posx.value = x.toFixed(2);
      if (posy) posy.value = y.toFixed(2);

      var form = document.getElementById("form-" + vista);
      if (form) {
        form.hidden = false;
        form.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
    });
  });
});

function cancelarMarcador(vista) {
  var form = document.getElementById("form-" + vista);
  if (form) form.hidden = true;
}
