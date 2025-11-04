<template>
<div class="admin-page">
  <div class="action-menu">
    <h3>All Domains</h3>
  </div>
  <div class="domains-table position-relative">
    <b-table v-if="domains.length" sort-by="domain" striped hover :items="domains" :fields="fields">
      <template v-slot:cell(domain)="row">
        {{ row.value }}
      </template>
      <template v-slot:cell(type)="row">
        <b-badge :variant="row.value === 'Project' ? 'primary' : 'info'">{{ row.value }}</b-badge>
      </template>
      <template v-slot:cell(name)="row">
        {{ row.value }}
      </template>
      <template v-slot:cell(active)="row">
        <b-badge :variant="row.value?'success':'warning'">{{row.value?'active':'inactive'}}</b-badge>
      </template>
      <template v-slot:cell(actions)="row">
        <b-button v-if="row.item.type === 'Project'" variant="primary" size="sm" :href="'/admin/project/'+row.item.project_uid">Edit Project</b-button>
        <b-button v-if="row.item.type === 'Redirect'" variant="primary" size="sm" :href="'/admin/redirect/'+row.item.name">Edit Redirect</b-button>
      </template>
    </b-table>
    <div v-else class="text-center p-4">
      <p>No domains found.</p>
    </div>
  </div>
</div>
</template>

<script>

import { mapState } from 'vuex';

export default {

  data: () => ({
    domains: domains,
    fields: [
      {key: 'domain', label: 'Domain', sortable: true },
      {key: 'type', label: 'Type', sortable: true },
      {key: 'name', label: 'Name', sortable: true },
      {key: 'active', label: 'Status', sortable: true },
      {key: 'actions', label: 'Actions'}
    ]
  }),

  computed: {

    localComputed () {

    },

    ...mapState({

      actual: state => state.actual

    })

  }

}

</script>
