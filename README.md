# Ansible Role: Rustdesk Server/Client Installs

An Ansible Role that install [Rustdesk](https://github.com/rustdesk/rustdesk) and [Rustdesk-Server](https://github.com/rustdesk/rustdesk-server) for  [LUDUS](https://ludus.cloud/).  When clients are installed they will checkin with server that has a python server running on port 8000 (default).  Users can browse to this port to see all hosts that have checked in and quickly start the rustdesk session with the uri handler "rustdesk://".  Additionally on the site is a button to copy the configuration string to be pasted into rustdesk's Network settings.

## Requirements

None.

## Role Variables
```yaml
# Server configuration
rustdesk_admin_user: "rustdeskadmin"
rustdesk_admin_password: "rustdeskadmin" 
rustdesk_install_dir: "/opt/rustdesk"

# Client configuration
rustdesk_server_ip: ""
rustdesk_client_password: "rustdeskclientpassword"
http_port: 8000 
rustdesk_clientid: ""

rustdesk_server: false
rustdesk_client: false
```

## Dependencies

None.

## Example Playbook

## Example Ludus Range Config

```yaml
ludus:
  - vm_name: "Win11-24h2"
    hostname: "Win11-24h2"
    template: win11-24h2-x64-template
    vlan: 10
    ip_last_octet: 20
    ram_gb: 8
    cpus: 4
    windows:
      sysprep: true
    roles:
      - name: ludus_rustdesk
        depends_on:
          - vm_name: PL-rustdesk
            role: ludus_rustdesk
    role_vars:
      rustdesk_client: true
  - vm_name: "{{ range_id }}-rustdesk"
    hostname: "{{ range_id }}-rustdesk"
    template: debian-12-x64-server-template
    vlan: 10
    ip_last_octet: 2
    ram_gb: 8
    cpus: 4
    linux: true
    testing:
      snapshot: false
      block_internet: false
    roles:
      - ludus_rustdesk
    role_vars:
      rustdesk_server: true
```

## License

GPLv3

## Author Information

This role was created by [beardhammer](https://github.com/Beardhammer), for [Ludus](https://ludus.cloud/).