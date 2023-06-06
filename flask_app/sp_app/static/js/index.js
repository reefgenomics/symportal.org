// Media query
let vp_width_match = window.matchMedia("(max-width: 560px)");
let vp_height_match = window.matchMedia("(max-height: 500px)");

// // Even listeners for the mouse enter and leave
// let showcase_content_enter_listener = document.getElementById("showcase_content").addEventListener("mouseenter", blur_nav_bar);
// let showcase_content_leave_listener = document.getElementById("showcase_content").addEventListener("mouseleave", unblur_nav_bar);

// Init the datatable
$(document).ready(function() {
    $('#published_articles_table').DataTable(
        {
            scrollX: true,
            scrollY: 400,
            scrollCollapse: true,
            paging: false,
            // https://datatables.net/reference/option/dom
            "dom": 'lrt<"d-flex m-0 p-0"<"col mr-auto p-0"i><"col p-0"f>>p'
        }
    );
    
    $('#resources_table').DataTable(
        {
            scrollX: true,
            scrollY: 400,
            scrollCollapse: true,
            paging: false,
            // https://datatables.net/reference/option/dom
            "dom": 'lrt<"d-flex m-0 p-0"<"col mr-auto p-0"i>>p'
        }
    );

    $('#unpublished_articles_table').DataTable(
        {
            scrollY: 400,
            scrollCollapse: true,
            paging: false,
            // https://datatables.net/reference/option/dom
            "dom": 'lrt<"d-flex m-0 p-0"<"col mr-auto p-0"i><"col p-0"f>>p'
        }
    );
} );

