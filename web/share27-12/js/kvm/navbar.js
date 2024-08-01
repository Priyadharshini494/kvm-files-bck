const zoomInButton = document.getElementById('zoomInButton');
const zoomOutButton = document.getElementById('zoomOutButton');
const myImage = document.getElementById('stream-image3');

let zoomLevel = 100; // Initial zoom level in percentage
// Function to set the zoom level of the image
 function setZoomLevel(level) {
   myImage.style.transform = `scale(${level / 100})`;
   }


  zoomInButton.addEventListener('click', function () {
     // Increase the zoom level by 10%
       zoomLevel += 10;
         setZoomLevel(zoomLevel);
       });

    zoomOutButton.addEventListener('click', function () {
             // Increase the zoom level by 10%
         zoomLevel -= 10;
         setZoomLevel(zoomLevel);
         });

function ZoomIn(button) {
    button.innerHTML = `<img src="/share/svg/zoom-in.svg" >Zoom-In`;
}
function ZoomOut(button) {
    button.innerHTML = `<img src="/share/svg/zoom-out.svg" >Zoom-Out`;
}
function RightButton(button) {
  button.innerHTML = `<img src="/share/svg/move-right.svg" >Right`;
}
function LeftButton(button) {
  button.innerHTML = `<img src="/share/svg/move-left.svg" >Left`;
}
function UpButton(button) {
  button.innerHTML = `<img src="/share/svg/move-up.svg" >Up`;
}
function DownButton(button) {
  button.innerHTML = `<img src="/share/svg/move-down.svg" >Down`;
}
function AutofocusButton(button) {
  button.innerHTML = `<img src="" >Auto-focus`;
}
function FocusInButton(button) {
  button.innerHTML = `<img src="" >FocusIn`;
}
function FocusOutButton(button) {
  button.innerHTML = `<img src" >FocusOut`;
}
      



function resetZoomIn(button) {
    button.innerHTML = `<img src="/share/svg/zoom-in.svg">`;
}
function resetZoomOut(button) {
    button.innerHTML =  `<img src="/share/svg/zoom-out.svg" >`;
}
function resetRight(button) {
  button.innerHTML = `<img src="/share/svg/move-right.svg">`;
}
function resetLeft(button) {
  button.innerHTML =  `<img src="/share/svg/move-left.svg" >`;
}
function resetUp(button) {
  button.innerHTML = `<img src="/share/svg/move-up.svg">`;
}
function resetDown(button) {
  button.innerHTML =  `<img src="/share/svg/move-down.svg" >`;
}
function resetAutoFocus(button) {
  button.innerHTML = "";
}
function resetFocusIn(button) {
  button.innerHTML = "";
}
function resetFocusOut(button) {
  button.innerHTML = "";
}


function enableDetach() {
  // Enable the Detach button
  document.getElementById("detachButton").disabled = false;

  document.getElementById("attachButton").disabled = true;
}

function detach() {
  
  // Disable the Detach button
  document.getElementById("detachButton").disabled = true;
  
  // Enable the Attach button
  document.getElementById("attachButton").disabled = false;
}
