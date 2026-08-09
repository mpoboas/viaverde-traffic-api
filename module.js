
var radarMarkers = new Array();
var cameraMarkers = new Array();
var alertMarkers = new Array();

var map, radarCluster, cameraCluster, camSelectedCode, camSelectedTitle, infowindow, alertLink, timeout, interval;

function initEvents() {

    $('.info-box-wrapper .cam-vv-service').load(function () {
        onImageLoad();
    });

    $('.close_btn').click(function (e) {
        e.preventDefault();
        $(this).parents().eq(2).hide();

        clearTimeout(timeout);
    });

    $(".js-openServices").on('click', function (e) {
        e.stopPropagation();

        if ($(this).hasClass('active')) {

            //remove class on clicked element
            $(this).removeClass("active");
            //remove class on clicked element - change arrow
            $(this).children('.btn-arrow').removeClass('up');
            //remove class on clicked element - hide/close dropdown
            $(this).next().removeClass('active');
            //remove class on clicked element - change z-index
            $(this).parents('.services-wrapper').removeClass('active');

        } else {

            if (document.getElementById("alert-list")) {
                document.getElementById("alert-list").removeAttribute("style");
            }

            //remove class on all elements
            $(".js-openServices").removeClass('active');
            //remove class on all elements - change arrows
            $(".js-openServices").children('.btn-arrow').addClass('up');
            //remove class on all elements - hide/close dropdown
            $(".js-openServices").next().removeClass('active');
            //remove class on all elements - to change z-index
            $(".js-openServices").parents('.services-wrapper').removeClass('active');

            //add class on clicked element
            $(this).addClass("active");
            //add class on clicked element - change arrow
            $(this).children('.btn-arrow').addClass('up');
            //add class on clicked element - open dropdown
            $(this).next().addClass('active');
            //add class on clicked element - to change z-index
            $(this).parents('.services-wrapper').addClass('active');
        }


        //scrollpane();
    });

    $(".scroll_pane_link").hover(function () {
        $(this).find('.scroll_pane_arrow').toggleClass("scroll_pane_arrow_active");
    });

    $('#selectHighways').change(function (e) {
        selectCameraGroup();
    });

    $('#selectCamera').change(function (e) {
        goToCamera();
    });
}

/********************************************************************/
/*                           MAP FUNCTIONS                          */
/********************************************************************/
var mapZoom = 7;

function initTraffic() {
    var mapOptions = {
        mapTypeId: google.maps.MapTypeId.ROADMAP,
        zoom: mapZoom,
        panControl: false,
        scrollwheel: false,
        mapTypeControl: false,
        zoomControl: true,
        zoomControlOptions: {
            style: google.maps.ZoomControlStyle.SMALL,
            position: google.maps.ControlPosition.RIGHT_BOTTOM
        },
        rotateControl: false
    };

    map = new google.maps.Map(document.getElementById('map-canvas'), mapOptions);
    map.setOptions({ styles: mapStyles });

    var trafficLayer = new google.maps.TrafficLayer();
    trafficLayer.setMap(map);

    var bounds = new google.maps.LatLngBounds();

    populateRadars(bounds);
    populateCameras(bounds);
    populateAlerts(bounds);

    google.maps.event.addListener(map, 'mousedown', function () {
        this.setOptions({ scrollwheel: true });
    });
    google.maps.event.addListener(map, 'mouseout', function () {
        this.setOptions({ scrollwheel: false });
    });

    setTimeout(function () {
        if (!bounds.isEmpty()) {
            map.fitBounds(bounds);
            var listener = google.maps.event.addListenerOnce(map, 'idle', function () {
                if (map.getZoom() > mapZoom) {
                    map.setZoom(mapZoom);
                }
            });
        } else {
            // Fallback center if no data yet
            var geocoder = new google.maps.Geocoder();
            geocoder.geocode({ address: 'Portugal' }, function (results, status) {
                if (status === google.maps.GeocoderStatus.OK) {
                    map.setCenter(results[0].geometry.location);
                    map.setZoom(mapZoom);
                }
            });
        }
        hideLoading();
    }, 500);
}
function Marker(id, lat, lng, type, content) {
    this.id = id;
    this.lat = lat;
    this.lng = lng;
    this.type = type;
    this.content = content;
    this.gmarker = null;
}

function addMarker(marker, map, title) {
    var location = new google.maps.LatLng(marker.lat, marker.lng);
    var markerImage = {
        url: icons[marker.type].icon,
        origin: new google.maps.Point(0, 0),
        anchor: new google.maps.Point(36, 40)
    };

    var markerTitle = marker.content;
    if (!!markerTitle) {
        markerTitle = title;
    }

    var googleMarker = new google.maps.Marker({
        position: location,
        icon: markerImage,
        map: map,
        title: markerTitle,
        clickable: true
    });

    if (marker.type === 'camera') {
        googleMarker.set('code', marker.id);

        google.maps.event.addListener(googleMarker, 'click', function () {
            camSelectedCode = googleMarker.get('code');
            camSelectedTitle = googleMarker.title;
            selectCameraById(camSelectedCode);
        });
    } else {
        if (infowindow == null) {
            infowindow = new google.maps.InfoWindow({
                content: marker.content
            });
        }

        google.maps.event.addListener(googleMarker, 'click', function () {
            infowindow.setContent('<div class="infoWindow radar">' + marker.content + '</div>');
            infowindow.open(map, googleMarker);
        });
    }

    return googleMarker;
}

function getResponseItems(data) {
    if (!data) {
        return [];
    }

    if ($.isArray(data)) {
        return data;
    }

    if ($.isArray(data.Items)) {
        return data.Items;
    }

    return [];
}

function normalizeAlert(alert) {
    if (!alert) {
        return null;
    }

    var latitude = alert.coordinates ? alert.coordinates.latitude : alert.latitude;
    var longitude = alert.coordinates ? alert.coordinates.longitude : alert.longitude;
    var id = alert.id != null ? alert.id : alert.idIncidencia;
    var description = alert.description || alert.descricaoIncidencia;
    var roadId = alert.roadId != null ? alert.roadId : alert.HighwayId;
    var roadName = alert.roadName || alert.HighwayName;
    var alertType = alert.alertType || alert.tipoIncidencia;
    var status = alert.status || '';
    var isResolved = status === "Resolução" || status === "Resolu��o" || status === "Resolução" || alert.dataFimIncidencia !== "";

    return {
        id: id,
        description: description,
        roadId: roadId,
        roadName: roadName,
        latitude: latitude,
        longitude: longitude,
        isAccident: alertType === "Acidente" || alertType === 1,
        isResolved: isResolved
    };
}

function normalizeCamera(camera) {
    if (!camera) {
        return null;
    }

    var latitude = camera.coordinates ? camera.coordinates.latitude : camera.Latitude;
    var longitude = camera.coordinates ? camera.coordinates.longitude : camera.Longitude;

    return {
        id: camera.id != null ? camera.id : camera.idCamara,
        name: camera.name || camera.nomeCamara,
        roadName: camera.roadName || camera.nomeAe,
        latitude: latitude,
        longitude: longitude,
        imageUrl: camera.imageUrl
    };
}

/********************************************************************/
/*                           ALERTS FUNCTIONS                       */
/********************************************************************/

function populateAlerts(bounds) {
    $.ajax({
        type: 'GET',
        url: apiUrl,
        data: { action: 'trafficalerts', lang: currentLanguage },
        dataType: 'json',
        processData: true,
        cache: false,
        beforeSend: function (request, settings) {
            sf.setModuleHeaders(request);
        },
        success: function (data, textStatus, jqXHR) {
            populateAlertsComplete(getResponseItems(data), bounds);
        },
        error: function (request, status, error) {
        },
        complete: function () {
        }
    });
}

function populateAlertsComplete(data, bounds) {
    var html = '';
    var htmlSlider = '';

    $('.js-alertBoxWrapper').show();
    if (!!data) {
        $.each(data, function (i, alert) {
            var normalizedAlert = normalizeAlert(alert);
            var type = '';

            if (!normalizedAlert) {
                return;
            }

            if (normalizedAlert.isAccident) {
                type = 'red_alert';
            }
            else {
                type = 'yellow_alert';
            }

            if (normalizedAlert.isResolved) {
                type = 'green_alert';
            }

            var markerContent = "<p>" + normalizedAlert.description + "</p>";
            if (alertsUrl !== "") {
                alertLink = "<a target='_blank' class='link-add-map' href='" + alertsUrl + "/id/" + normalizedAlert.roadId + "'>" + alertUrlCopy + normalizedAlert.roadName + "</a>";
                markerContent = markerContent + alertLink;
            }

            var marker = new Marker(normalizedAlert.id, normalizedAlert.latitude, normalizedAlert.longitude, type, markerContent);
            var gmarker = addMarker(marker, map, normalizedAlert.description);

            marker.gmarker = gmarker;
            alertMarkers.push(gmarker);

            alerts[normalizedAlert.id] = marker;

            html = html + '<div class="alerts-box d-flex" onclick="goToAlert(' + normalizedAlert.id + ');"><div class="' + type + '_icon left col-1"></div><div class="col-11"><p>' + normalizedAlert.description + '</p></div></div>';

            htmlSlider = htmlSlider + '<li onclick="goToAlert(' + normalizedAlert.id + ');"><div class="' + type + '_icon left"></div><p>' + normalizedAlert.description + '</p></li>';

            var point = new google.maps.LatLng(normalizedAlert.latitude, normalizedAlert.longitude);
            bounds.extend(point);
        });
    }


    $('.services-box-panel .scroll-pane').append(html);
    $('.js-alertList').append(htmlSlider);
}

function closeAlertsBox() {
    if ($('.js-alertBoxWrapper .js-openServices').hasClass('active')) {

        $('.js-alertBoxWrapper .js-openServices').next().slideUp("slow", function () {
            $('.js-alertBoxWrapper .js-openServices').stop().animate('slow', function () {
                $('.js-alertBoxWrapper .js-openServices').removeClass("active");
                $('.js-alertBoxWrapper .js-openServices').children(".js-alertList").removeClass("active");
            });
        });
        $('.js-alertBoxWrapper .js-openServices').children('.btn-arrow').removeClass('up');
    }
}

function goToAlert(id) {
    closeCamerasBox();
    closeAlertsBox();

    var marker = alerts[id].gmarker;

    map.setZoom(17);
    map.panTo(marker.getPosition());

    google.maps.event.trigger(marker, 'click');
}

/********************************************************************/
/*                           CAMARA FUNCTIONS                       */
/********************************************************************/

function populateCameras(bounds) {
    $.ajax({
        type: 'GET',
        url: apiUrl,
        data: { action: 'cameras', lang: currentLanguage },
        dataType: 'json',
        processData: true,
        cache: false,
        beforeSend: function (request) {
            sf.setModuleHeaders(request);
        },
        success: function (data, textStatus, jqXHR) {
            populateCamerasComplete(getResponseItems(data), bounds);
        },
        error: function (request, status, error) {
        },
        complete: function () {
        }
    });
}

var cameraGroup = new Array();
function populateCamerasComplete(data, bounds) {
    var html = '';

    $('.js-cameraBox').show();

    //Group cameras by highway
    if (!!data) {
        for (var i = 0; i < data.length; i++) {
            var camera = normalizeCamera(data[i]);

            if (!camera) {
                continue;
            }

            //Exists
            if (cameraGroup[camera.roadName]) {
                cameraGroup[camera.roadName].push(camera);
            }
            else {
                cameraGroup[camera.roadName] = new Array();
                cameraGroup[camera.roadName].push(camera);
            }
        }
    }

    //Show groups
    for (var key in cameraGroup) {
        var group = cameraGroup[key];
        html += '<option value="' + key + '">' + group[0].roadName + '</option>';
    }

    $('#selectHighways').append(html);
    initSelect($('#selectHighways'));
    selectCameraGroup();
    //initSelect($('#selectCamera'));
    //$('#selectHighways').select2({
    //    placeholder: "" + selectHighwayPlaceholder + "",
    //    minimumResultsForSearch: Infinity, width: '100%'
    //});

    if (!!data) {
        //Load camera data in the map
        $.each(data, function (index, cameraJSON) {
            var camera = normalizeCamera(cameraJSON);
            if (!camera) {
                return;
            }

            var marker = new Marker(camera.id, camera.latitude, camera.longitude, 'camera', camera.name);
            var gmarker = addMarker(marker, map);

            cameraMarkers.push(gmarker);

            var point = new google.maps.LatLng(camera.latitude, camera.longitude);
            bounds.extend(point);
        });
    }

    var img = iconBase + 'cameracluster.png';

    var mcOptions = {
        zoom: mapZoom,
        styles: [{
            height: 56,
            url: img,
            width: 42,
            anchor: [37, 19],
            iconAnchor: [38, 40],
            backgroundPosition: [0, 0],
            textColor: '#ffffff',
            textSize: 10
        }]
    };

    cameraCluster = new MarkerClusterer(map, cameraMarkers, mcOptions);
}

function selectCameraById(id) {

    //Check if camera box is open
    if (!$('.js-cameraBox .js-openServices').hasClass('active')) {
        $('.js-cameraBox .js-openServices').click();
    }
    var key;
    //Show groups
    for (key in cameraGroup) {
        for (var i = 0; i < cameraGroup[key].length; i++) {
            var camera = cameraGroup[key][i];
            if (camera.id === id) {
                $("#selectHighways").val(key);
                selectCameraGroup();
                $("#selectCamera").val(i);
                goToCamera();
                return;
            }
        }
    }
}

function selectCameraGroup() {
    var key = $("#selectHighways").val();
    if (key) {
        var html = '';
        for (var i = 0; i < cameraGroup[key].length; i++) {
            var camera = cameraGroup[key][i];
            html += '<option value=' + i + '>' + camera.name + '</option>';
        }

        $('#selectCamera').html(html);
        $("#selectCamera").prop("disabled", false);
        $("#selectCamera").val("0");
        $("#selectCamera").select2();
        goToCamera();
    }
    else {

        $("#selectCamera").val("");
        $("#selectCamera").empty();
        $("#selectCamera").prop("disabled", true);
        $("#selectCamera").select2();
    }
}

function goToCamera() {
    var key = $("#selectHighways").val();
    var i = $("#selectCamera").val();
    if (i && key) {
        var camera = cameraGroup[key][i];
        var latLng = new google.maps.LatLng(camera.latitude, camera.longitude);

        map.setZoom(17);
        map.panTo(latLng);

        $('.info-box-wrapper').addClass("ic-cam-loading");
        $('.info-box-wrapper .cam-vv-service').attr("src", "");
        showCam(camera);
    }
    updatePrevNextButtons();
}

function updatePrevNextButtons() {

    var key = $("#selectHighways").val();
    var i = $("#selectCamera").val();
    if (i && key && cameraGroup[key].length > 1) {
        if (i === 0) {
            $("#btnPrevCamera").prop("disabled", true);
            $("#btnNextCamera").prop("disabled", false);
        }
        else if (i === cameraGroup[key].length - 1) {
            $("#btnNextCamera").prop("disabled", true);
            $("#btnPrevCamera").prop("disabled", false);
        }
        else {
            $("#btnPrevCamera").prop("disabled", false);
            $("#btnNextCamera").prop("disabled", false);
        }
    }
    else {
        $("#btnPrevCamera").prop("disabled", true);
        $("#btnNextCamera").prop("disabled", true);
    }
}

function onImageLoad() {
    $('.info-box-wrapper').removeClass("ic-cam-loading");
}

function showCam(cameraInfo) {
    clearTimeout(timeout);

    $('.services-box-panel .info-box-wrapper').show();
    if (cameraInfo && cameraInfo.imageUrl) {
        var img = cameraInfo.imageUrl;

        if (/^https?:\/\//i.test(img)) {
            $('.info-box-wrapper .cam-vv-service').attr('src', img);
        } else {
            $('.info-box-wrapper .cam-vv-service').attr('src', 'data:image/jpeg;base64,' + img);
        }
    }

    timeout = setTimeout(function () { showCam(cameraInfo) }, 30000);
}

function closeCamerasBox() {
    if ($('.js-cameraBox .js-openServices').hasClass('active')) {

        $('.js-cameraBox .js-openServices').next().slideUp("slow", function () {
            $('.js-cameraBox .js-openServices').stop().animate('slow', function () {
                $('.js-cameraBox .js-openServices').removeClass("active");
            });
        });

        $('.js-cameraBox .js-openServices').children('.btn-arrow').removeClass('up');
    }
}

function closeCameraDetail() {
    if (!$('.services-box-panel .info-box-wrapper').is(':visible')) {
        $('.close_btn').parents().eq(2).hide();
        clearTimeout(timeout);

        $('.services-box-panel .info-box-wrapper').hide();

        $('.info-box-wrapper .cam-vv-service').attr("src", "");
        $("#selectHighways").val("");
        $('#selectHighways').select2({
            placeholder: "" + selectHighwayPlaceholder + "",
            minimumResultsForSearch: Infinity, width: '100%'
        });
        selectCameraGroup();
    }
}

function nextCamera() {
    var i = Number($("#selectCamera").val()) + 1;
    $("#selectCamera").val(i);
    $("#selectCamera").select2().change();
}

function prevCamera() {
    var i = Number($("#selectCamera").val()) - 1;
    $("#selectCamera").val(i);
    $("#selectCamera").select2().change();
}

/********************************************************************/
/*                            RADAR FUNCTIONS                       */
/********************************************************************/


function populateRadars(bounds) {
    $.ajax({
        type: 'GET',
        url: apiUrl,
        data: { action: 'trafficradars', lang: currentLanguage },
        dataType: 'json',
        processData: true,
        cache: false,
        beforeSend: function (xhr) {
            sf.setModuleHeaders(xhr);
        },
        success: function (data, textStatus, jqXHR) {
            populateRadarsComplete(data, bounds);
        },
        error: function (request, status, error) {
        },
        complete: function () {
        }
    });
}

function populateRadarsComplete(data, bounds) {
    if (!!data) {

        $.each(data, function (i, radar) {
            var markerContent = "";
            //// TODO :: insert client-side html for the content
            if (!!jsSettings) {
                /*
                 <span class="tit">Radar</span>
                                <div class="cont-wrapper">
                                    <span class="ae">A25</span>
                                    <span class="route">Lisboa <span class="divisor">></span> Porto</span>
                                </div>
                                <div class="lat-long">
                                    <span class="lat"><strong>Latitude:</strong>38,79893859</span>
                                    <span class="long"><strong>Longitude:</strong>38,79893859</span>
                                    <span class="pk"><strong>PK:</strong>21.00</span>
                                </div>
                */

                if (!!jsSettings.RadarTitle) {
                    markerContent = "<span class='tit'>" + jsSettings.RadarTitle + "</span>";
                }

                markerContent += "<div class='cont-wrapper'>";
                markerContent += "<span class='ae'>" + radar.Title + "</span>";
                markerContent += "<span class='route'>" + radar.Direction + "</span>";
                markerContent += "<span class='limit'>" + radar.SpeedLimit + "</span>";
                markerContent += "</div><div class='lat-long'>";

                if (!!jsSettings.RadarLatitude) {
                    markerContent += " <span class='lat'><strong>" + jsSettings.RadarLatitude + ":</strong>" + radar.Latitude + "</span>";
                }

                if (!!jsSettings.RadarLongitude) {
                    markerContent += "<span class='long'><strong>" + jsSettings.RadarLongitude + ":</strong>" + radar.Longitude + "</span>";
                }

                if (!!jsSettings.RadarKmPoint) {
                    markerContent += "<span class='pk'><strong>" + jsSettings.RadarKmPoint + ":</strong>" + radar.KmPoint + "</span>";
                }

                markerContent += "</div>";
            }

            var type = 'radar';

            var marker = new Marker(radar.id, radar.Latitude, radar.Longitude, type, markerContent);
            //// Note:: this is to remove the html comming from server-side
            var noHtmlDirection = $("<p>" + radar.Direction + "</p>").text();
            var gmarker = addMarker(marker, map, jsSettings.RadarTitle + " " + radar.Title + " " + noHtmlDirection);

            marker.gmarker = gmarker;

            radarMarkers.push(gmarker);

            var point = new google.maps.LatLng(radar.Latitude, radar.Longitude);
            bounds.extend(point);
        });
    }

    var img = iconBase + 'icone_radar_group.png';

    var mcOptions = {
        zoom: mapZoom,
        styles: [{
            height: 56,
            url: img,
            width: 42,
            anchor: [37, 19],
            iconAnchor: [38, 40],
            backgroundPosition: [0, 0],
            textColor: '#ffffff',
            textSize: 10
        }]
    };

    radarCluster = new MarkerClusterer(map, radarMarkers, mcOptions);
}


function closeFilterBox() {
    if ($('.filters_box_wrapper .box_slide').hasClass('box_slide_active')) {

        $('.filters_box_wrapper .box_slide').next().slideUp("slow", function () {
            $('.filters_box_wrapper .box_slide').stop().animate('slow', function () {
                $('.filters_box_wrapper .box_slide').removeClass("box_slide_active");
            });
        });

        $('.filters_box_wrapper .box_slide').children('.btn_down').removeClass('btn_up');
    }
}

/********************************************************************/
/*                           Helper FUNCTIONS                       */
/********************************************************************/


function scrollpane() {
    $('.scroll-pane').jScrollPane({
        showArrows: false,
        animateScroll: true,
        autoReinitialise: true
    });
}

function toggleMarkers(sender, category) {
    var visible = $(sender).is(':checked');

    if (category === 'radar') {
        setMarkersVisible(radarMarkers, visible);
        radarCluster.setMap(visible ? map : null);
    } else if (category === 'alert') {
        setMarkersVisible(alertMarkers, visible);
        if (visible) {
            $(".js-alertBoxWrapper").show(300);
        }
        else {
            $(".js-alertBoxWrapper").hide(300);
        }
    }
    else {
        setMarkersVisible(cameraMarkers, visible);
        cameraCluster.setMap(visible ? map : null);
        if (visible) {
            $(".js-cameraBox").show(300);
        }
        else {
            $(".js-cameraBox").hide(300);
        }
    }
}

function setMarkersVisible(markers, visible) {
    for (var i = 0; i < markers.length; i++) {
        markers[i].setVisible(visible);
    }
}

window.addEventListener('load', function () {
    initTraffic();
});


$(function () {
    showLoading();

    google.maps.event.addDomListener(window, 'onload', initTraffic);// Added for bug search
    google.maps.event.addDomListener(window, 'resize', initTraffic);// Added for bug search

    var $slider = $('.js-alertList');
    var $slide = 'li';
    var $transition_time = 1000;
    var $time_between_slides = 4000;

    function slides() {
        return $slider.find($slide);
    }

    slides().fadeOut();

    slides().first().addClass('active');
    slides().first().fadeIn($transition_time);

    $interval = setInterval(
        function () {
            var $i = $slider.find($slide + '.active').index();

            slides().eq($i).removeClass('active');
            //slides().eq($i).fadeOut($transition_time);

            if (slides().length == $i + 1) $i = -1;

            //slides().eq($i + 1).fadeIn($transition_time);
            slides().eq($i + 1).addClass('active');
        }
        , $transition_time + $time_between_slides
    );

    initEvents();
});

function showLoading() {
    $("#trafficLoading").show();
}

function hideLoading() {
    $("#trafficLoading").hide();
}