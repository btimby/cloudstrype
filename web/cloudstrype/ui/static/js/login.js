$(function() {
    $('#form-signin li').click(function() {
        $('#form-signin li').removeClass('form-signin-selected');
        $this = $(this);
        $('#form-signin-provider').val($this.attr('class'));
        $this.addClass('form-signin-selected');
    });
});