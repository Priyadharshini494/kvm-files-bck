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

